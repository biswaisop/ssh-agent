"""
Critic agent node — safety gate before every END in the LangGraph.

Architecture rules (from ARCHITECTURE.md §9 + §15):

  BLOCK   — rm -rf /, dd, mkfs, shutdown, chmod /etc/*, wildcard destroys
  CONFIRM — rm <file>, kill/pkill, systemctl stop, apt remove, sudo state ops
  ALLOW   — reads, lists, stats, installs (-y), /tmp writes, non-destructive

The critic runs on a SEPARATE, more capable llm (Sonnet-level reasoning).
For the current stack this means a separate ChatGroq instance at temperature=0
so the safety check is never traded off for speed or cost.

LangGraph integration:
    graph.add_node("critic", critic_node)

The node returns the updated state dict. Callers should check state["confirmed"]
and route accordingly — CONFIRM pauses the graph and awaits a user "yes".
Pending confirmation data is stored in Redis with a 60-second TTL.
"""
import json
import logging
import re
from typing import Literal
import os

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_groq import ChatGroq
from dotenv import load_dotenv

from connectors.redis_connector import SessionMemoryService

load_dotenv()

logger = logging.getLogger(__name__)

# ── Critic LLM — use best available model, temperature=0, no shortcuts ────────
# Per architecture: "Critic runs on Sonnet (not Haiku) — no shortcuts on safety"
# We use the most capable Groq model available at temp=0.
_critic_llm = ChatGroq(
    model=os.getenv("CRITIC_MODEL", "llama-3.3-70b-versatile"),
    temperature=0,
    api_key=os.getenv("GROQ"),
)

# ── System prompt — plain string (no f-string) to avoid brace interpolation ───
CRITIC_SYSTEM_PROMPT = """\
You are a safety-critical Linux command reviewer for a remote SSH agent system.

Your job: inspect what the agent just did or proposes to do and decide if it is safe.

You will receive:
- user_intent: the original user request
- agent_response: the agent's last message (includes commands it ran or is proposing)

Respond ONLY with a single valid JSON object — no explanation, no markdown, no extra text.

Output schema:
{
  "decision": "ALLOW | CONFIRM | BLOCK",
  "risk_level": "low | medium | high",
  "reason": "one-line explanation",
  "user_message": "message shown to user (empty string for ALLOW)"
}

--- RULES ---

ALLOW (low risk — execute immediately):
- Read-only: ls, cat, find, ps, df, free, uptime, ping, curl (GET), top, pwd, whoami, echo, grep
- Package installs with apt-get install -y or pip install
- Writing new files to /tmp or /workspace
- Running scripts: python3, bash, node in /workspace
- Any clearly additive, non-destructive operation

CONFIRM (medium risk — require explicit user "yes"):
- rm targeting a SPECIFIC named file or directory (not a wildcard)
- kill / pkill targeting a specific named process or PID
- systemctl stop / disable / restart for a named service
- apt remove / pip uninstall
- mv of files with important-looking names (configs, keys, databases)
- Overwriting existing files outside /tmp
- Any sudo command that changes system state

BLOCK (high risk — refuse, no confirmation possible):
- rm -rf / or rm -rf ~ or rm -rf /* or any root-level wildcard delete
- dd if=... targeting a block device (if=/dev/...)
- mkfs.* formatting a disk
- shutdown / poweroff / reboot / halt
- chmod or chown on /etc/passwd, /etc/shadow, /etc/sudoers
- Fork bombs: :(){ :|:& };:
- Any command clearly designed to destroy or exfiltrate data


ADDITIONAL CONSTRAINTS:
- If the agent's response contains NO shell commands (just text), reply ALLOW.
- If scope is ambiguous → CONFIRM, not BLOCK.
- Never modify or correct the command — only judge it.
- CONFIRM user_message must clearly state: what will happen + what is affected.
  Example: "This will terminate process nginx (PID 1234). Reply YES to confirm."

--- EXAMPLES ---

agent_response contains: "ps aux --sort=-%cpu | head -10"
Output: {"decision":"ALLOW","risk_level":"low","reason":"read-only process list","user_message":""}

agent_response contains: "kill 1234"
Output: {"decision":"CONFIRM","risk_level":"medium","reason":"terminates a running process","user_message":"This will kill process with PID 1234. Reply YES to confirm."}

agent_response contains: "rm -rf /"
Output: {"decision":"BLOCK","risk_level":"high","reason":"system-wide destructive delete","user_message":"This action is permanently blocked for safety reasons."}
"""


# ── JSON extraction — handles LLM wrapping output in ```json ... ``` ──────────
def _parse_verdict(raw: str) -> dict:
    # Strip markdown code fences if present
    cleaned = re.sub(r"```(?:json)?", "", raw).strip()
    # Try to extract first {...} object
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    # Fail-safe: block on any parse failure
    logger.warning("Critic failed to parse LLM response: %s", raw[:200])
    return {
        "decision": "BLOCK",
        "risk_level": "high",
        "reason": "critic response could not be parsed — blocking for safety",
        "user_message": "Action blocked: internal safety check failed. Please try again.",
    }


# ── Public evaluate function (sync, reusable outside LangGraph) ───────────────

def evaluate_command(user_intent: str, proposed_command: str) -> dict:
    """
    Synchronously evaluate a proposed bash command.

    Used by the critic node in graph.py before any command is executed.
    Returns a verdict dict:
      {decision, risk_level, reason, user_message}
    Fail-safe: any exception → BLOCK.
    """
    try:
        response = _critic_llm.invoke([
            SystemMessage(content=CRITIC_SYSTEM_PROMPT),
            HumanMessage(content=(
                f"user_intent: {user_intent}\n\n"
                f"proposed_command: {proposed_command}"
            )),
        ])
        return _parse_verdict(response.content)
    except Exception as exc:
        logger.error("evaluate_command failed: %s", exc)
        return {
            "decision":     "BLOCK",
            "risk_level":   "high",
            "reason":       f"critic unavailable: {exc}",
            "user_message": "Action blocked: safety check unavailable. Please try again.",
        }


# ── LangGraph node ─────────────────────────────────────────────────────────────
async def critic_node(state: dict) -> dict:
    """
    LangGraph node — runs after the agent finishes (no more tool calls).

    Reads the agent's last message, calls the critic LLM, and handles:
      ALLOW   → pass through, graph proceeds to END
      CONFIRM → store pending in Redis (60s TTL), append confirmation request
      BLOCK   → append blocked message
    """
    # ── 1. Extract last agent message ─────────────────────────────────────────
    last = state["messages"][-1]
    agent_response = str(getattr(last, "content", ""))

    # Also capture any tool calls in the message for full context
    tool_calls = getattr(last, "tool_calls", [])
    if tool_calls:
        commands = [tc.get("args", {}).get("command", "") for tc in tool_calls]
        agent_response += "\n\nCommands executed: " + " | ".join(filter(None, commands))

    # ── 2. Get original user intent (first HumanMessage) ──────────────────────
    user_intent = ""
    for msg in state["messages"]:
        if isinstance(msg, HumanMessage):
            user_intent = str(msg.content)
            break

    # ── 3. Skip check if user already confirmed ────────────────────────────────
    if state.get("confirmed"):
        logger.info("critic_node: confirmed=True, skipping safety check")
        return state

    # ── 4. Call critic LLM ─────────────────────────────────────────────────────
    try:
        response = _critic_llm.invoke([
            SystemMessage(content=CRITIC_SYSTEM_PROMPT),
            HumanMessage(content=(
                f"user_intent: {user_intent}\n\n"
                f"agent_response: {agent_response}"
            )),
        ])
        verdict = _parse_verdict(response.content)
    except Exception as exc:
        logger.error("Critic LLM call failed: %s", exc)
        verdict = {
            "decision": "BLOCK",
            "risk_level": "high",
            "reason": f"critic unavailable: {exc}",
            "user_message": "Action blocked: safety check unavailable. Please try again.",
        }

    decision = verdict.get("decision", "BLOCK").upper()
    logger.info(
        "critic verdict: %s | risk: %s | reason: %s",
        decision, verdict.get("risk_level"), verdict.get("reason"),
    )

    # ── 5. Handle verdict ──────────────────────────────────────────────────────
    if decision == "ALLOW":
        # Nothing to do — graph proceeds to END normally
        pass

    elif decision == "CONFIRM":
        user_id = state.get("user_id", "unknown")
        pending_data = {
            "user_intent": user_intent,
            "agent_response": agent_response,
            "verdict": verdict,
        }
        # Store in Redis with 60s TTL (per architecture §15)
        try:
            svc = SessionMemoryService()
            await svc.store_pending_confirm(user_id, pending_data)
        except Exception as exc:
            logger.error("Failed to store pending confirmation in Redis: %s", exc)

        confirm_msg = verdict.get(
            "user_message",
            "⚠️ This is a potentially destructive operation. Reply YES to confirm."
        )
        state["messages"].append(AIMessage(content=f"⚠️ {confirm_msg}"))

    elif decision == "BLOCK":
        block_msg = verdict.get(
            "user_message",
            "This action has been permanently blocked for safety reasons."
        )
        state["messages"].append(
            AIMessage(content=f"🚫 Blocked: {block_msg}")
        )

    return state