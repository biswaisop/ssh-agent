import pytest
from fastapi.testclient import TestClient
import json

# Import the FastAPI app from main.py
from main import app

def test_websocket_chat_allow_flow():
    """
    Test a harmless command that should be ALLOWED automatically
    without hitting the confirmation interrupt.
    """
    # The context manager (`with`) ensures app lifespan events run (like connecting to Redis)
    with TestClient(app) as client:
        # Connect to the agent endpoint for ubuntu on localhost
        with client.websocket_connect("/api/ws/ubuntu/localhost") as websocket:
            
            # 1. Verify the initial connection greeting
            connect_data = websocket.receive_json()
            assert connect_data["type"] == "info"
            assert "Connected to GenOS Agent" in connect_data["content"]
            
            # 2. Send a completely safe command
            websocket.send_json({"message": "who am i?"})
            
            # 3. Read stream until execution is finished
            messages = []
            while True:
                response = websocket.receive_json()
                messages.append(response)
                
                if response["type"] == "output":
                    break # Done executing
                elif response["type"] == "error":
                    pytest.fail(f"Agent returned error: {response['content']}")
                elif response["type"] == "confirm":
                    pytest.fail("Safe command unexpectedly triggered a CONFIRM prompt")
                    
            # 4. Verify the final result
            output_msg = messages[-1]
            assert output_msg["type"] == "output"
            assert "Command executed" in output_msg["content"]


def test_websocket_chat_confirm_flow():
    """
    Test a potentially dangerous command that MUST trigger the confirmation flow,
    and then reject it to verify cancellation works.
    """
    with TestClient(app) as client:
        with client.websocket_connect("/api/ws/ubuntu/localhost") as websocket:
            
            # Skip initial greeting
            websocket.receive_json()
            
            # 1. Send risky command
            websocket.send_json({"message": "systemctl stop nginx"})
            
            # 2. Wait for CONFIRM prompt
            confirm_triggered = False
            while True:
                response = websocket.receive_json()
                
                if response["type"] == "confirm":
                    confirm_triggered = True
                    # Verify it correctly identified the risk
                    assert response["risk_level"] in ("medium", "high")
                    break
                elif response["type"] == "output":
                    pytest.fail("Dangerous command executed without triggering confirmation!")
                elif response["type"] == "error":
                    pytest.fail(f"Agent returned error: {response['content']}")
                    
            assert confirm_triggered is True
            
            # 3. Send "no" to cancel the execution
            websocket.send_json({"resume": "no"})
            
            # 4. Await final output message indicating cancellation
            cancelled_msg = None
            while True:
                response = websocket.receive_json()
                if response["type"] == "output":
                    cancelled_msg = response
                    break
                    
            assert "[CANCELLED]" in cancelled_msg["content"]
            assert "Action cancelled" in cancelled_msg["content"]
