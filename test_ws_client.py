import asyncio
import websockets
import json

async def chat():
    uri = "ws://localhost:8000/api/ws/ubuntu/localhost"
    print(f"Connecting to {uri} ...")
    
    try:
        async with websockets.connect(uri) as websocket:
            print("Connected!")
            
            # Receive initial connection info
            msg = await websocket.recv()
            print(f"> {json.loads(msg).get('content', '')}")

            while True:
                user_input = input("\nYou: ").strip()
                if not user_input:
                    continue
                if user_input.lower() in ('quit', 'exit'):
                    break
                
                # Heuristic: if input is literally yes/no, send it as `resume`
                # (For a real UI, this would be a specific Confirm button)
                if user_input.lower() in ('yes', 'no'):
                    await websocket.send(json.dumps({"resume": user_input}))
                else:
                    await websocket.send(json.dumps({"message": user_input}))
                
                # Read stream until execution is finished or paused
                while True:
                    try:
                        response_str = await websocket.recv()
                        data = json.loads(response_str)
                    except Exception as e:
                        print(f"[ERROR parsing JSON]: {e}")
                        break
                    
                    msg_type = data.get("type")
                    
                    if msg_type == "info":
                        print(f"[INFO] {data.get('content')}")
                        
                    elif msg_type == "output":
                        print(f"\n[AGENT RESPONDED]")
                        print(data.get("content"))
                        break # Cycle done, go back to prompt
                        
                    elif msg_type == "confirm":
                        print(f"\n[⚠️  HUMAN APPROVAL REQUIRED - Risk: {data.get('risk_level', '').upper()}]")
                        print(data.get("message"))
                        print("Type 'yes' or 'no' to decide.")
                        break # Yield to prompt so user can type yes/no
                        
                    elif msg_type == "error":
                        print(f"\n[ERROR] {data.get('content')}")
                        break # Cycle done
                        
    except Exception as e:
        print(f"WebSocket connection failed: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(chat())
    except KeyboardInterrupt:
        print("\nExiting.")
