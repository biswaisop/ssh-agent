# test_graph.py
"""
Quick automated test — runs a few natural language commands through the full graph.
Non-interactive: only tests SAFE (ALLOW) commands so no confirmation prompt appears.
"""
import asyncio
from dotenv import load_dotenv
load_dotenv()

from config import settings
from graph import run

HOST     = settings.SSH_HOST
USERNAME = settings.SSH_USERNAME


async def test():
    cases = [
        "what is my CPU usage?",
        "list files in /var/log",
        "what processes are running?",
        "how much disk space is left?",
        # "Delete the authorized_keys from .ssh"
    ]

    for msg in cases:
        print(f"\n{'-'*50}")
        print(f">  {msg}")
        print('-'*50)
        try:
            result = await run(message=msg, hostname=HOST, username=USERNAME)
            print(result)
        except Exception as exc:
            print(f"[ERROR] {exc}")


if __name__ == "__main__":
    asyncio.run(test())