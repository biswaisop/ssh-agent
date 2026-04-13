from config import settings
import textwrap

def format_output(command: str, result: dict) -> str:
    stdout = result.get("stdout", "")[:settings.MAX_STDOUT_CHARS]
    stderr = result.get("stderr", "")[:2000]
    exit_code = result.get('exit_code')

    output = f"""COMMAND: {command}

STDOUT:
{stdout if stdout.strip() else '[Empty]'}

STDERR:
{stderr if stderr.strip() else '[None]'}

EXIT CODE:
{exit_code}"""
    
    return output