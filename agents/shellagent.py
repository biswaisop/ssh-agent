"""
Planner node for the GenOS agent graph.

Responsibility: given the user's natural language message, call the correct
command-generator tool and return the proposed bash command in state.

It does NOT execute the command — that happens in the executor node,
and only after the critic clears it.

Generator tools available:
  create_os_command      → general shell, scripts, package management
  create_file_tool       → file / directory operations
  create_process_command → process monitoring, kill, service management
  create_network_command → network diagnostics, curl, ping, ss
"""
import logging

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from langgraph.prebuilt import ToolNode

from brain.llm import llm
from tools.all_tools import all_tools as GENERATOR_TOOLS

logger = logging.getLogger(__name__)

# ── Prompt ────────────────────────────────────────────────────────────────────

PLANNER_PROMPT = """\
You are a Linux command planner for a remote SSH agent.

Given the user's request, call EXACTLY ONE of your tools to generate the
appropriate bash command. The tool will return the raw bash command string.

Tool selection guide:
  create_os_command      → general shell, run scripts, package management (apt, pip)
  create_file_tool       → ls, find, cp, mv, rm, mkdir, cat, zip, tar
  create_process_command → ps, kill, pkill, systemctl, uptime, top
  create_network_command → ping, curl, wget, ss, netstat, ip, dig

Rules:
- Call ONE tool only — do not chain tools.
- Pass the user's request as the "command" argument.
- Pass recent conversation context as the "context" argument (list of strings).
- Do NOT attempt to execute anything yourself.
"""

# ── Tool node (generator tools only — no run_command) ─────────────────────────
_generator_tool_node = ToolNode(GENERATOR_TOOLS)


# ── Planner node ──────────────────────────────────────────────────────────────

def planner_node(state: dict) -> dict:
    """
    LangGraph node.

    1. Binds generator tools to the LLM (tool_choice='any' forces a tool call).
    2. Calls the selected tool to get the proposed bash command.
    3. Returns the proposed command in state — does NOT execute it.
    """
    messages = state.get("messages", [])

    # ── RAG context from ChromaDB (injected by context_retrieval_node) ────────
    rag_context: str = state.get("context", "")

    # Build context list: RAG results first, then recent conversation turns
    context_parts = []
    if rag_context:
        context_parts.append(rag_context)
    context_parts += [
        str(m.content)
        for m in messages[-4:]
        if hasattr(m, "content") and m.content
    ]

    # ── Step 1: LLM picks the right generator tool ─────────────────────────────
    system = PLANNER_PROMPT
    if rag_context:
        system += f"\n\nContext from previous interactions:\n{rag_context}"

    llm_with_tools    = llm.bind_tools(GENERATOR_TOOLS, tool_choice="any")
    planning_messages = [SystemMessage(content=system)] + messages

    ai_response = llm_with_tools.invoke(planning_messages)

    tool_names = [tc["name"] for tc in (ai_response.tool_calls or [])]
    logger.info("planner tool calls: %s", tool_names)
    tool_used = tool_names[0] if tool_names else "unknown"

    # ── Step 2: Execute the selected generator tool ────────────────────────────
    new_messages     = [ai_response]
    proposed_command = ""

    if ai_response.tool_calls:
        # Patch the context arg into the tool call so the inner LLM sees it
        for tc in ai_response.tool_calls:
            if "context" in tc.get("args", {}):
                tc["args"]["context"] = context_parts

        tool_input_state = {"messages": messages + [ai_response]}
        tool_result      = _generator_tool_node.invoke(tool_input_state)
        tool_msg: ToolMessage = tool_result["messages"][-1]

        new_messages.append(tool_msg)
        proposed_command = tool_msg.content.strip()

        logger.info("planner proposed command: %s", proposed_command)
    else:
        # Fallback: LLM wrote command directly in content
        proposed_command = ai_response.content.strip()
        logger.warning("planner made no tool call — using content as command")

    return {
        "messages":         new_messages,
        "proposed_command": proposed_command,
        "tool_used":        tool_used,
    }