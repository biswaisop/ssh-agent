"""
RAG ingestion and retrieval service for SSH session memory.

Two responsibilities:
  1. ingest_interaction() — called AFTER a command executes successfully.
     Embeds the (intent, command, output) triple with enriched metadata
     and stores it in the user's ChromaDB collection.

  2. get_context() — called BEFORE the planner runs.
     Semantically searches past interactions relevant to the current user query
     and returns a formatted string ready for injection into the planner prompt.

Usage in graph:
    # Before planner:
    ctx = get_context(user_id, user_message)
    state["context"] = ctx

    # After executor:
    ingest_interaction(user_id, intent, command, output, verdict, risk, tool)
"""
import logging
from typing import Optional

from connectors.chroma_connector import SSHMemoryStore

logger = logging.getLogger(__name__)


def ingest_interaction(
    user_id:         str,
    intent:          str,
    command:         str,
    output:          str,
    critic_decision: str = "ALLOW",
    risk_level:      str = "low",
    tool_used:       str = "unknown",
) -> dict:
    """
    Embed and store one completed command interaction.

    Called from the executor node in graph.py after a command runs successfully.
    Silently swallows errors so a ChromaDB failure never breaks the main flow.

    Args:
        user_id:         "username@hostname"
        intent:          Original user natural language request
        command:         Bash command that was executed
        output:          Raw output from connector.exec()
        critic_decision: ALLOW | CONFIRM | BLOCK
        risk_level:      low | medium | high
        tool_used:       Which generator tool produced the command

    Returns:
        {"status": "success", "id": "..."} or {"status": "failed", "error": "..."}
    """
    try:
        store = SSHMemoryStore(user_id)
        result = store.ingest(
            intent=intent,
            command=command,
            output=output,
            critic_decision=critic_decision,
            risk_level=risk_level,
            tool_used=tool_used,
        )
        logger.info(
            "RAG ingested for %s: [%s] %s → %s",
            user_id, critic_decision, intent[:50], command
        )
        return result
    except Exception as e:
        logger.error("RAG ingest failed for %s: %s", user_id, e)
        return {"status": "failed", "error": str(e)}


def get_context(
    user_id: str,
    query:   str,
    k:       int = 5,
) -> str:
    """
    Retrieve semantically relevant past interactions for the current query.

    Called from the context_retrieval node in graph.py before the planner runs.
    Returns an empty string if no relevant history exists yet (first-time user).
    Always safe to call — silently returns "" on any error.

    Args:
        user_id: "username@hostname"
        query:   The user's current natural language message
        k:       Max number of past interactions to retrieve

    Returns:
        Formatted multi-line context string, or "" if nothing relevant found.

    Example return value:
        Relevant past interactions on ubuntu@localhost:
        [1] (2026-04-20) "check disk space" → df -h
             Output: Filesystem Size Used Avail Use% Mounted on overlay 1007G...
        [2] (2026-04-20) "list log files" → ls /var/log
             Output: alternatives.log apt bootstrap.log btmp dpkg.log...
    """
    try:
        store   = SSHMemoryStore(user_id)
        results = store.search(query, k=k)
        context = store.format_context(results)

        if context:
            logger.info(
                "RAG retrieved %d interactions for '%s' on %s",
                len(results), query[:50], user_id,
            )
        else:
            logger.debug("RAG: no relevant context found for '%s'", query[:50])

        return context
    except Exception as e:
        logger.error("RAG retrieval failed for %s: %s", user_id, e)
        return ""
