from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command
from langchain_core.messages import HumanMessage, AIMessage
import json
import logging

from graph import build_graph, State

router = APIRouter()
logger = logging.getLogger(__name__)

# Global checkpointer for development (in-memory state)
checkpointer = MemorySaver()

# Cache compiled graphs per host/user
compiled_graphs = {}

def get_agent_graph(hostname: str, username: str):
    graph_id = f"{username}@{hostname}"
    if graph_id not in compiled_graphs:
        compiled_graphs[graph_id] = build_graph(hostname, username, checkpointer=checkpointer)
    return compiled_graphs[graph_id]

@router.websocket("/ws/{username}/{hostname}")
async def agent_websocket(websocket: WebSocket, username: str, hostname: str):
    """
    WebSocket endpoint for full interactive agent communication.
    Supports chat messages and handles LangGraph `interrupt()` pauses.
    """
    await websocket.accept()
    
    agent_graph = get_agent_graph(hostname, username)
    thread_id = f"{username}@{hostname}"
    thread_config = {"configurable": {"thread_id": thread_id}}
    
    logger.info(f"WebSocket connected for {thread_id}")
    await websocket.send_json({"type": "info", "content": f"Connected to GenOS Agent on {thread_id}"})
    
    try:
        while True:
            data = await websocket.receive_text()
            
            try:
                payload = json.loads(data)
            except json.JSONDecodeError:
                # Fallback to pure string if not JSON
                payload = {"message": data}
                
            # If payload has 'resume', it's answering a CONFIRM prompt
            if "resume" in payload:
                decision = payload["resume"].strip().lower()
                
                # Verify if the graph is actually paused
                snapshot = agent_graph.get_state(thread_config)
                if snapshot.next:
                    await websocket.send_json({"type": "info", "content": f"Resuming with your decision: {decision}"})
                    
                    try:
                        result = await agent_graph.ainvoke(Command(resume=decision), config=thread_config)
                    except Exception as e:
                        logger.error(f"Error resuming graph: {e}")
                        await websocket.send_json({"type": "error", "content": f"Execution error: {e}"})
                        continue
                else:
                    await websocket.send_json({"type": "error", "content": "No pending confirmation found. Please send a new command."})
                    continue
            else:
                # Normal command payload
                message = payload.get("message", "")
                if not message:
                    await websocket.send_json({"type": "error", "content": "Received empty message."})
                    continue
                
                init_state: State = {
                    "messages":         [HumanMessage(content=message)],
                    "user_id":          thread_id,
                    "context":          "",
                    "proposed_command": "",
                    "tool_used":        "",
                    "critic_verdict":   {},
                    "approved":         False,
                    "execution_output": "",
                }
                
                await websocket.send_json({"type": "info", "content": "Agent is processing..."})
                
                try:
                    result = await agent_graph.ainvoke(init_state, config=thread_config)
                except Exception as e:
                    logger.error(f"Error invoking graph: {e}")
                    await websocket.send_json({"type": "error", "content": f"Graph execution error: {e}"})
                    continue
                
            # Post execution/resume: Check if paused for human approval again
            snapshot = agent_graph.get_state(thread_config)
            
            if snapshot.next:
                # We hit an interrupt
                interrupt_val = snapshot.tasks[0].interrupts[0].value
                await websocket.send_json({
                    "type": "confirm",
                    "message": interrupt_val.get("message", "Confirm this action?"),
                    "command": interrupt_val.get("proposed_command", ""),
                    "risk_level": interrupt_val.get("risk_level", "medium")
                })
            else:
                # Finished executing completely
                # Extract the last AI message
                found_msg = False
                for msg in reversed(result["messages"]):
                    if isinstance(msg, AIMessage) and msg.content:
                        await websocket.send_json({"type": "output", "content": msg.content})
                        found_msg = True
                        break
                
                if not found_msg:
                    await websocket.send_json({"type": "output", "content": "Task completed (no message returned)."})
                        
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for {thread_id}")
    except Exception as e:
        logger.error(f"WebSocket unhandled error: {e}")
