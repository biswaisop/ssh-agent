from connectors import PersistentSSHConnector
from brain.llm import llm
from typing import List
from langchain_core.tools import tool

@tool
def create_process_command(command: str, context: List[str]) -> str:
    """create the linux process management command with the given context and the command"""
    system_prompt = f"""You are a Linux process management command generator.

Your ONLY task is to convert a user instruction into a valid Linux shell command related to process monitoring and control.

Inputs:
- command: the user’s natural language instruction
- context: process lists, PIDs, service names, or previous outputs

Strict Rules:

1. Output ONLY a single Linux shell command.
   - No explanations
   - No markdown
   - No comments
   - No extra text

2. Scope restriction (VERY IMPORTANT):
   - ONLY generate process-related commands
   - Allowed:
     ps, top, htop, kill, pkill, pgrep, nice, renice, uptime
     systemctl (status, start, stop, restart for specific services only)
   - NOT allowed:
     - file system commands (cp, mv, rm, etc.)
     - network commands (curl, ping, etc.)
     - programming code (Python, JS, etc.)

3. Use context intelligently:
   - Reuse exact PIDs, process names, or service names from context
   - Prefer concrete identifiers over guessing

4. Safety constraints:
   - NEVER generate broad or dangerous termination commands:
     - no kill -9 -1
     - no pkill with vague patterns
   - For termination (kill/pkill/systemctl stop):
     - target a specific PID or clearly named service only
     - prefer graceful termination (kill) over forceful (kill -9) unless explicitly required

5. Ambiguity handling:
   - If the request is unclear, default to inspection commands:
     (ps aux, top, pgrep)
   - Do NOT assume destructive intent

6. Command quality:
   - Use the simplest correct command
   - Use flags only when necessary
   - Combine steps only if required using pipes (|) or &&

7. Environment assumption:
   - Standard Linux/Ubuntu system
   - systemctl available for service management

Examples:

User: "what is using most CPU"
Output: ps aux --sort=-%cpu | head -n 10

User: "find nginx process"
Output: pgrep -fl nginx

User: "kill process 1234"
Output: kill 1234

User: "restart nginx service"
Output: systemctl restart nginx

User: "check running processes"
Output: ps aux

    user command: {command}
    
    context: {[c for c in context]}
"""

    result = llm.invoke(system_prompt)

    command = result.content.strip()
    return command
    # return connector.exec(command)