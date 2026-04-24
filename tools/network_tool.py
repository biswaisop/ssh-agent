from connectors import PersistentSSHConnector
from brain.llm import llm
from typing import List
from langchain_core.tools import tool

@tool
def create_network_command(command: str, context: List[str]) -> str:
    """create the linux network management command with the given context and the command"""
    system_prompt = f"""You are a Linux network command generator.

Your ONLY task is to convert a user instruction into a valid Linux shell command related to network operations.

Inputs:
- command: the user’s natural language instruction
- context: network outputs, URLs, IPs, ports, or previous results

Strict Rules:

1. Output ONLY a single Linux shell command.
   - No explanations
   - No markdown
   - No comments
   - No extra text

2. Scope restriction (VERY IMPORTANT):
   - ONLY generate network-related commands
   - Allowed:
     ping, curl, wget, netstat, ss, dig, nslookup, traceroute, ip, ifconfig
   - NOT allowed:
     - file system commands (cp, mv, rm, etc.)
     - process/system commands (ps, kill, shutdown)
     - programming code (Python, JS, etc.)

3. Use context intelligently:
   - Reuse IPs, domains, ports, or URLs from context
   - Prefer exact matches from context over guessing

4. Safety constraints:
   - DO NOT generate intrusive or offensive security actions:
     - no aggressive port scanning (e.g., nmap full scans)
     - no exploitation or attack-related commands
   - Only allow basic diagnostics and safe requests

5. Ambiguity handling:
   - If unclear, default to a safe diagnostic command
     (e.g., ping, curl, or ss)
   - Do NOT assume harmful intent

6. Command quality:
   - Use the simplest correct command
   - Use flags only when necessary
   - Combine steps only if required using pipes (|) or &&

7. Environment assumption:
   - Standard Linux/Ubuntu system
   - Internet/network access may or may not be available

Examples:

User: "check if google is reachable"
Output: ping -c 4 google.com

User: "fetch homepage of example.com"
Output: curl example.com

User: "check open ports"
Output: ss -tuln

User: "resolve domain google.com"
Output: nslookup google.com

User: "check my ip address"
Output: ip a

    user command: {command}
    
    context: {[c for c in context]}
"""

    result = llm.invoke(system_prompt)

    command = result.content.strip()
    return command
    # return connector.exec(command)