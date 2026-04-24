"""
Terminal REPL for GenOS — tests the full generate → critic → confirm → execute flow.

Usage:
    python quick_test.py

Reads SSH_HOST / SSH_USERNAME from config (set in .env or config.py defaults).
Type 'exit' or 'quit' to stop.
"""
import asyncio
from dotenv import load_dotenv
load_dotenv()

from config import settings
from graph import run

HOST     = settings.SSH_HOST
USERNAME = settings.SSH_USERNAME


async def main():
    print("╔══════════════════════════════════════════════════╗")
    print("║           GenOS Terminal  —  SSH Agent           ║")
    print(f"║  Connected to: {USERNAME}@{HOST:<32}║")
    print("╠══════════════════════════════════════════════════╣")
    print("║  Type a natural language command.  'exit' quits  ║")
    print("╚══════════════════════════════════════════════════╝\n")

    while True:
        try:
            user_message = input("You › ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            break

        if not user_message:
            continue
        if user_message.lower() in ("exit", "quit", "q"):
            print("Bye.")
            break

        print()
        try:
            response = await run(
                message=user_message,
                hostname=HOST,
                username=USERNAME,
            )
            print(f"Agent »\n{response}\n")
        except Exception as exc:
            print(f"[ERROR] {exc}\n")


if __name__ == "__main__":
    asyncio.run(main())