from agents.shellagent import create_agent

if __name__ == "__main__":
    agent = create_agent()
    
    while True:
        user_input = input("\n>>> ")
        if user_input.lower() in ["exit", "quit"]:
            break
        try:
            response = agent.invoke({"input": user_input})
            print("\n", response)
        except Exception as e:
            print("Error:", str(e))