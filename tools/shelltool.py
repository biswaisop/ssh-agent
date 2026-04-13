from langchain.tools import tool

from connectors.ssh import run_command_ssh
from utils.formatter import format_output
from config import settings

@tool
def shell_tool(command: str) -> str:
    """Execute a shell command on the remote machine and return its output."""
    result = run_command_ssh(
        host=settings.SSH_HOST,
        port=settings.SSH_PORT,
        username=settings.SSH_USERNAME,
        key_path=settings.KEY_PATH,
        password=settings.PASSWORD,
        command=command
    )

    return format_output(command, result)