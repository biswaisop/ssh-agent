from langchain_classic.agents import create_react_agent, AgentExecutor
from langchain_core.prompts import PromptTemplate
from brain.llm import llm

from tools.shelltool import shell_tool

def create_agent():
    tools = [shell_tool]
    
    template = """You are a helpful Linux system assistant.
Your goal is to answer the user's question by executing shell commands on a remote machine.

You have access to the following tools:
{tools}

Use the following format:

Question: the input question you must answer
Thought: you should always think about what to do
Action: the action to take, should be one of [{tool_names}]
Action Input: the command
Observation: the result of the action
... (this Thought/Action/Action Input/Observation can repeat N times)
Thought: I now know the final answer
Final Answer: the final answer to the original input question

IMPORTANT RULES:
1. ALWAYS use non-interactive flags for commands. For example:
   - Use 'apt-get install -y' instead of 'apt install'
   - Use 'apt-get upgrade -y' instead of 'apt upgrade'
2. Prefix administrative commands with 'DEBIAN_FRONTEND=noninteractive' if needed.
3. If a command times out, it likely requires interactive input. Try again with '-y' or a different approach.
4. Do not repeat the Question in your thoughts.

Begin!

Question: {input}
Thought: {agent_scratchpad}"""

    prompt = PromptTemplate.from_template(template)

    agent = create_react_agent(
        llm=llm,
        tools=tools,
        prompt=prompt
    )
    
    executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        handle_parsing_errors=True,
        max_iterations=5
    )
    
    return executor