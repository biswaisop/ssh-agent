from pydantic import BaseModel, Field
from langchain_core.tools import tool
from connectors import PersistentSSHConnector
from brain.llm import llm
from typing import List


@tool
def create_os_command(command: str, context: List[str]) -> str:
    """Generate a Linux OS shell command from a natural language instruction and context."""

    system_prompt = f"""You are a Linux OS command generator.

Your ONLY task is to convert a user instruction into a valid Linux shell command.

Inputs:
- command: the user's natural language instruction
- context: system outputs, environment details, or previous results

Strict Rules:

1. Output ONLY a single Linux shell command.
   - No explanations
   - No markdown
   - No comments
   - No extra text

2. Scope restriction:
   - ONLY generate OS-level commands (shell, file system, process, network, package management)
   - DO NOT generate application-level code (Python, JS, SQL, etc.)

3. Valid command categories:
   - File operations (ls, cp, mv, find, du, df)
   - Process management (ps, top, kill, pkill)
   - System monitoring (free, uptime, top)
   - Networking (ping, curl, netstat, ss)
   - Package management (apt, apt-get)
   - Permissions (chmod, chown)

4. Use context when relevant:
   - Reuse file paths, process IDs, service names from context

5. Safety constraints:
   - NEVER generate: rm -rf /, mkfs.*, dd if=..., shutdown, reboot, poweroff
   - For risky actions: limit scope strictly, avoid wildcards

6. If unclear: default to a safe inspection command.

Examples:
User: "what is using most CPU"  → ps aux --sort=-%cpu | head -n 10
User: "check disk usage"        → df -h
User: "kill process 1234"       → kill 1234

user command: {command}
context: {context}"""

    result = llm.invoke(system_prompt)
    return result.content.strip()
