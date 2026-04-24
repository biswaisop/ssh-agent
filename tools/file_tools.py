from connectors import PersistentSSHConnector
from brain.llm import llm
from typing import List
from langchain_core.tools import tool


@tool
def create_file_tool(command: str, context: List[str]) -> str:
    """create the linux file management command with the given context and the command"""
    system_prompt = f"""You are a Linux file management command generator.

Your ONLY task is to convert a user instruction into a valid Linux shell command related to file and directory operations.

Inputs:
- command: the user’s natural language instruction
- context: file paths, directory listings, or previous outputs

Strict Rules:

1. Output ONLY a single Linux shell command.
   - No explanations
   - No markdown
   - No comments
   - No extra text

2. Scope restriction (VERY IMPORTANT):
   - ONLY generate file system operations
   - Allowed:
     ls, find, cp, mv, rm, mkdir, rmdir, touch, cat, less, head, tail, du, tree, zip, unzip, tar
   - NOT allowed:
     - process commands (ps, kill, top)
     - system commands (shutdown, reboot)
     - network commands (curl, ping)
     - programming code (Python, JS, etc.)

3. Use context intelligently:
   - Reuse exact file names, directories, or paths from context
   - Avoid guessing paths if context provides them

4. Safety constraints:
   - NEVER generate dangerous commands like:
     rm -rf /
     rm -rf ~
   - For delete operations:
     - limit scope strictly to specific files or directories
     - avoid wildcards (*) unless clearly safe
     - prefer safer alternatives if ambiguous (e.g., list files first)

5. Ambiguity handling:
   - If the request is unclear, default to a safe read/list operation (ls, find)
   - Do NOT assume destructive intent

6. Command quality:
   - Use the simplest correct command
   - Use flags only when necessary
   - Combine steps only if required using pipes (|) or &&

7. Environment assumption:
   - Standard Linux/Ubuntu system
   - Files are primarily within accessible user directories (e.g., /workspace)

Examples:

User: "list all files"
Output: ls -la

User: "find all python files"
Output: find . -type f -name "*.py"

User: "copy file1.txt to backup folder"
Output: cp file1.txt backup/

User: "delete temp.txt"
Output: rm temp.txt

User: "zip all logs"
Output: zip logs.zip *.log

    user command: {command}
    
    context: {[c for c in context]}
"""

    result = llm.invoke(system_prompt)

    command = result.content.strip()
    return command
    # return connector.exec(command)