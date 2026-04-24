"""
Minimal smoke test — verifies the LLM + generator tools work before running the full graph.
"""
import os
import asyncio
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage

from config import settings
from connectors.session_manager import get_connector
from tools.all_tools import all_tools as GENERATOR_TOOLS

load_dotenv()


async def test_groq():
    connector = get_connector(settings.SSH_HOST, settings.SSH_USERNAME)

    llm = ChatGroq(
        model=settings.MODEL,
        temperature=0,
        api_key=settings.GROQ,
    )

    llm_with_tools = llm.bind_tools(GENERATOR_TOOLS)

    try:
        messages = [
            {"role": "system", "content": "Pick the right tool and generate a bash command."},
            {"role": "user",   "content": "what is using the most CPU right now?"},
        ]
        response = llm_with_tools.invoke(messages)
        print("Response:", response.content)
        print("Tool calls:", response.tool_calls)
    except Exception as e:
        print("Exception:", str(e))


if __name__ == "__main__":
    asyncio.run(test_groq())
