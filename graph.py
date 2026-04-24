# graph.py
"""
GenOS agent graph — context → generate → critic → confirm → execute → ingest

Full flow:
  START
    │
    ▼
  context_retrieval    Semantic search over past interactions (ChromaDB RAG)
    │                  Injects relevant history into state["context"]
    ▼
  planner              LLM picks generator tool → proposed bash command
    │                  Passes state["context"] as the tool's context arg
    ▼
  critic               evaluate_command() checks command BEFORE execution
    │
    ├─ BLOCK   ──► END
    │
    └─ ALLOW / CONFIRM
         │
         ▼
       human_approval
         │ ALLOW  → approved = True (no interruption)
         │ CONFIRM → interrupt() → user types yes/no
         │
         ├─ rejected ──► END
         │
         └─ approved
               │
               ▼
             executor     connector.exec(proposed_command) via SSH
               │
               ▼
             ingestion    Embed (intent, command, output) into ChromaDB
               │
               ▼
             END
"""
import logging
from typing import Annotated, Literal

from typing_extensions import TypedDict
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.types import interrupt
from dotenv import load_dotenv

from connectors.session_manager import get_connector
from agents.shellagent import planner_node
from agents.criticagent import evaluate_command
from services.rag_service import get_context, ingest_interaction

load_dotenv()

logger = logging.getLogger(__name__)


# ── State ─────────────────────────────────────────────────────────────────────

class State(TypedDict):
    messages:         Annotated[list, add_messages]
    user_id:          str
    context:          str    # RAG-retrieved past interactions
    proposed_command: str    # bash command from planner
    tool_used:        str    # which generator tool was used
    critic_verdict:   dict   # {decision, risk_level, reason, user_message}
    approved:         bool   # True once human (or auto-) approved
    execution_output: str    # raw SSH output (for ingestion)


# ── 1. Context retrieval node ─────────────────────────────────────────────────

def context_retrieval_node(state: State) -> dict:
    """
    Semantic search over past interactions BEFORE the planner runs.
    Retrieves up to 5 relevant past (intent, command, output) triples.
    Sets state["context"] — planner passes it to the generator tool.
    """
    user_id = state.get("user_id", "")

    # Extract latest user message as the search query
    query = ""
    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage):
            query = str(msg.content)
            break

    if not query:
        return {"context": ""}

    context = get_context(user_id=user_id, query=query, k=5)
    logger.info("context_retrieval: %d chars retrieved", len(context))
    return {"context": context}


# ── 2. Planner node (context-aware) ───────────────────────────────────────────
# Imported from agents/shellagent.py, but we wrap it here to inject context.

def context_aware_planner(state: State) -> dict:
    """
    Wraps the planner node to inject RAG context into state before calling it,
    so the planner's generator tools receive the context list.
    """
    # The planner reads state["context"] and passes it as the context arg
    # to the generator tool — this is handled inside agents/shellagent.py
    return planner_node(state)


# ── 3. Critic node ────────────────────────────────────────────────────────────

def critic_node(state: State) -> dict:
    """
    Evaluate proposed_command BEFORE it executes.
    Appends a BLOCK message if blocked. Stores full verdict in state.
    """
    proposed = state.get("proposed_command", "")

    user_intent = ""
    for msg in state["messages"]:
        if isinstance(msg, HumanMessage):
            user_intent = str(msg.content)
            break

    verdict  = evaluate_command(user_intent, proposed)
    decision = verdict.get("decision", "BLOCK").upper()

    logger.info(
        "critic: %s | risk: %s | cmd: %s",
        decision, verdict.get("risk_level"), proposed,
    )

    new_messages = []
    if decision == "BLOCK":
        msg = verdict.get("user_message", "This action is permanently blocked.")
        new_messages.append(AIMessage(content=f"[BLOCKED] Blocked: {msg}"))

    return {
        "messages":      new_messages,
        "critic_verdict": verdict,
    }


def _route_after_critic(state: State) -> Literal["human_approval", "__end__"]:
    decision = state.get("critic_verdict", {}).get("decision", "BLOCK").upper()
    return END if decision == "BLOCK" else "human_approval"


# ── 4. Human approval node ────────────────────────────────────────────────────

def human_approval_node(state: State) -> dict:
    """
    ALLOW  → auto-approve, no interruption.
    CONFIRM → interrupt() pauses graph, caller handles terminal/Telegram prompt.
    """
    verdict  = state.get("critic_verdict", {})
    decision = verdict.get("decision", "ALLOW").upper()

    if decision == "ALLOW":
        return {"approved": True}

    confirm_msg = verdict.get(
        "user_message",
        f"Proceed with: `{state.get('proposed_command')}`? (yes/no)"
    )
    human_response: str = interrupt({
        "type":             "confirmation",
        "message":          confirm_msg,
        "proposed_command": state.get("proposed_command"),
        "risk_level":       verdict.get("risk_level"),
    })

    approved     = str(human_response).lower().strip() in ("yes", "y")
    new_messages = []
    if not approved:
        new_messages.append(AIMessage(content="[CANCELLED] Action cancelled."))

    return {"approved": approved, "messages": new_messages}


def _route_after_approval(state: State) -> Literal["executor", "__end__"]:
    return "executor" if state.get("approved") else END


# ── 5. Executor node ──────────────────────────────────────────────────────────

def make_executor(connector):
    def executor_node(state: State) -> dict:
        command = state.get("proposed_command", "")
        logger.info("executor: running → %s", command)

        output = connector.exec(command)

        return {
            "execution_output": output,
            "messages": [
                AIMessage(content=(
                    f"[OK] **Command executed:**\n```\n{command}\n```\n\n"
                    f"**Output:**\n```\n{output}\n```"
                ))
            ],
        }
    return executor_node


# ── 6. Ingestion node ─────────────────────────────────────────────────────────

def ingestion_node(state: State) -> dict:
    """
    Embed and store the completed interaction in ChromaDB after execution.
    Extracts intent, command, output, verdict, and tool_used from state.
    Never raises — failure is logged and silently swallowed.
    """
    user_id = state.get("user_id", "")
    verdict  = state.get("critic_verdict", {})

    # Find original user intent
    intent = ""
    for msg in state["messages"]:
        if isinstance(msg, HumanMessage):
            intent = str(msg.content)
            break

    ingest_interaction(
        user_id         = user_id,
        intent          = intent,
        command         = state.get("proposed_command", ""),
        output          = state.get("execution_output", ""),
        critic_decision = verdict.get("decision",   "ALLOW"),
        risk_level      = verdict.get("risk_level", "low"),
        tool_used       = state.get("tool_used",    "unknown"),
    )

    # Ingestion is a side-effect only — no state changes needed
    return {}


# ── Build ─────────────────────────────────────────────────────────────────────

def build_graph(hostname: str, username: str, checkpointer=None):
    """
    Returns a compiled LangGraph StateGraph.

    Pass checkpointer=MemorySaver() to enable interrupt() for CONFIRM flow.
    """
    connector = get_connector(hostname, username)

    g = StateGraph(State)

    g.add_node("context_retrieval", context_retrieval_node)
    g.add_node("planner",           context_aware_planner)
    g.add_node("critic",            critic_node)
    g.add_node("human_approval",    human_approval_node)
    g.add_node("executor",          make_executor(connector))
    g.add_node("ingestion",         ingestion_node)

    g.add_edge(START,              "context_retrieval")
    g.add_edge("context_retrieval","planner")
    g.add_edge("planner",          "critic")

    g.add_conditional_edges(
        "critic", _route_after_critic,
        {"human_approval": "human_approval", END: END},
    )
    g.add_conditional_edges(
        "human_approval", _route_after_approval,
        {"executor": "executor", END: END},
    )

    g.add_edge("executor",  "ingestion")
    g.add_edge("ingestion", END)

    return g.compile(checkpointer=checkpointer)


# ── Terminal runner ────────────────────────────────────────────────────────────

async def run(message: str, hostname: str, username: str) -> str:
    """
    High-level async runner for terminal / API use.
    Handles the CONFIRM interrupt loop automatically.
    """
    from langgraph.checkpoint.memory import MemorySaver
    from langgraph.types import Command

    checkpointer = MemorySaver()
    graph  = build_graph(hostname, username, checkpointer=checkpointer)
    thread = {"configurable": {"thread_id": f"{username}@{hostname}"}}

    init_state: State = {
        "messages":         [HumanMessage(content=message)],
        "user_id":          f"{username}@{hostname}",
        "context":          "",
        "proposed_command": "",
        "tool_used":        "",
        "critic_verdict":   {},
        "approved":         False,
        "execution_output": "",
    }

    result = await graph.ainvoke(init_state, config=thread)

    # Handle CONFIRM interrupt
    snapshot = graph.get_state(thread)
    if snapshot.next:
        interrupt_val = snapshot.tasks[0].interrupts[0].value

        print(f"\n{'─'*60}")
        print(f"⚠️  CONFIRMATION REQUIRED")
        print(f"   {interrupt_val.get('message', 'Confirm this action?')}")
        print(f"   Risk: {interrupt_val.get('risk_level', 'medium').upper()}")
        print(f"{'─'*60}")

        user_input = input("Your decision (yes / no): ").strip()
        result = await graph.ainvoke(Command(resume=user_input), config=thread)

    for msg in reversed(result["messages"]):
        if isinstance(msg, AIMessage) and msg.content:
            return msg.content

    return "Done."