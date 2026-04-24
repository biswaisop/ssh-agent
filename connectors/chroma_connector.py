"""
SSH-specific ChromaDB memory store.

Adapted from the previous project's Vector_store_service.

Key differences from the original:
  - No org_id — keyed by user_id = "username@hostname"
  - Collection name: ssh_{sanitized_user_id}  (e.g. ssh_ubuntu_localhost)
  - Client falls back to local PersistentClient when no CHROMADB_API_KEY is set
  - Documents represent command interactions, not knowledge-base chunks
  - Metadata schema is SSH-specific (intent, command, output, verdict, etc.)
  - ingest() replaces embed_documents() — takes raw strings, not LangChain Documents
  - search() replaces retrieve_documents() — threshold tuned for cosine distance (0–2 scale)
  - format_context() formats results as a plain string for LLM injection
"""
import os
import re
import uuid
import logging
from datetime import datetime, timezone
from typing import List, Dict, Optional

import chromadb
from chromadb.utils import embedding_functions
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ── Defaults ───────────────────────────────────────────────────────────────────
EMBEDDING_MODEL    = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")

# Cosine distance threshold — chromadb returns distances in [0, 2].
# 0 = identical, 1 = orthogonal, 2 = opposite.
# Values below 1.0 are semantically similar; we use 1.2 as a generous cutoff.
DEFAULT_DISTANCE_THRESHOLD = float(os.getenv("CHROMA_DISTANCE_THRESHOLD", "1.2"))


def _sanitize(user_id: str) -> str:
    """'ubuntu@54.206.74.122'  →  'ubuntu_54_206_74_122'"""
    return re.sub(r"[^a-zA-Z0-9_]", "_", user_id)


class SSHMemoryStore:
    """
    Per-user ChromaDB collection for SSH session memory.

    Each stored document represents one complete command interaction:
      text     → embedded: "User requested: ... | Command: ... | Output: ..."
      metadata → structured: intent, command, output snippet, verdict, timestamp, etc.

    Singleton client and embedding model are shared across all instances
    (same pattern as the original Vector_store_service).
    """

    _client: Optional[chromadb.Client] = None
    _embedding_fn = None

    # ── Singleton helpers ──────────────────────────────────────────────────────

    @classmethod
    def get_client(cls) -> chromadb.Client:
        if cls._client is None:
            api_key = os.getenv("CHROMADB_API_KEY")
            if api_key:
                # Cloud client (production)
                cls._client = chromadb.CloudClient(
                    tenant=os.getenv("CHROMADB_TENANT"),
                    api_key=api_key,
                    database=os.getenv("VECTOR_DB"), # force DB name expected by the server
                )
                logger.info("ChromaDB: using CloudClient")
            else:
                # Local persistent client (dev / no credentials)
                cls._client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
                logger.info("ChromaDB: using local PersistentClient at %s", CHROMA_PERSIST_DIR)
        return cls._client

    @classmethod
    def get_embedding_fn(cls):
        if cls._embedding_fn is None:
            cls._embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name=EMBEDDING_MODEL
            )
            logger.info("ChromaDB: embedding model loaded: %s", EMBEDDING_MODEL)
        return cls._embedding_fn

    # ── Init ──────────────────────────────────────────────────────────────────

    def __init__(self, user_id: str):
        self.user_id         = user_id
        self.collection_name = f"ssh_{_sanitize(user_id)}"
        self.client          = self.get_client()
        self.embedding_fn    = self.get_embedding_fn()

    # ── Collection ────────────────────────────────────────────────────────────

    def _get_collection(self):
        try:
            return self.client.get_or_create_collection(
                name=self.collection_name,
                embedding_function=self.embedding_fn,
                metadata={"hnsw:space": "cosine"},
            )
        except Exception as e:
            raise RuntimeError(
                f"Failed to get/create collection '{self.collection_name}': {e}"
            )

    # ── Ingestion ─────────────────────────────────────────────────────────────

    def ingest(
        self,
        intent:          str,
        command:         str,
        output:          str,
        critic_decision: str = "ALLOW",
        risk_level:      str = "low",
        tool_used:       str = "unknown",
    ) -> dict:
        """
        Embed and persist one command interaction.

        The embedded text combines intent + command + output so that semantic
        search on any of these surfaces this interaction.

        Returns:
            {"status": "success", "id": "<uuid>"} or {"status": "failed", "error": "..."}
        """
        collection = self._get_collection()

        # Text that gets embedded — rich enough for semantic retrieval
        output_snippet = output[:600] if output else ""
        document_text = (
            f"User requested: {intent}\n"
            f"Command executed: {command}\n"
            f"Server output: {output_snippet}"
        )

        doc_id   = str(uuid.uuid4())
        metadata = {
            "user_id":          self.user_id,
            "type":             "command_interaction",
            "user_intent":      intent[:500],
            "proposed_command": command[:300],
            "output_snippet":   output_snippet[:300],
            "critic_decision":  critic_decision,
            "risk_level":       risk_level,
            "tool_used":        tool_used,
            "timestamp":        datetime.now(timezone.utc).isoformat(),
            "success":          critic_decision in ("ALLOW", "CONFIRM"),
        }

        try:
            collection.add(
                ids=[doc_id],
                documents=[document_text],
                metadatas=[metadata],
            )
            logger.info(
                "ChromaDB ingested: [%s] %s → %s", risk_level.upper(), intent[:50], command
            )
            return {"status": "success", "id": doc_id}
        except Exception as e:
            logger.error("ChromaDB ingest failed: %s", e)
            return {"status": "failed", "error": str(e)}

    # ── Retrieval ─────────────────────────────────────────────────────────────

    def search(
        self,
        query:     str,
        k:         int   = 5,
        threshold: float = DEFAULT_DISTANCE_THRESHOLD,
    ) -> List[Dict]:
        """
        Semantic search over past command interactions.

        Args:
            query:     The user's natural language request (will be embedded).
            k:         Max results to return from ChromaDB before filtering.
            threshold: Max cosine distance to include (lower = more similar).
                       0 = identical, 1 = orthogonal, 2 = opposite.
                       Default 1.2 keeps clearly semantically related results.

        Returns:
            List of dicts: {intent, command, output_snippet, distance, timestamp, ...}
            Sorted by distance (most relevant first).
        """
        if not query or not query.strip():
            return []

        try:
            collection = self._get_collection()

            # Guard: don't query more than what's stored
            count = collection.count()
            if count == 0:
                return []
            n_results = min(k, count)

            raw = collection.query(
                query_texts=[query],
                n_results=n_results,
            )

            documents = raw.get("documents", [[]])[0]
            metadatas = raw.get("metadatas", [[]])[0]
            distances = raw.get("distances", [[]])[0]

            results = []
            for doc, meta, dist in zip(documents, metadatas, distances):
                if dist <= threshold:
                    results.append({
                        "document":  doc,
                        "metadata":  meta,
                        "distance":  dist,
                        # Convenience shortcuts
                        "intent":    meta.get("user_intent",      ""),
                        "command":   meta.get("proposed_command", ""),
                        "output":    meta.get("output_snippet",   ""),
                        "verdict":   meta.get("critic_decision",  ""),
                        "timestamp": meta.get("timestamp",        ""),
                    })

            results.sort(key=lambda r: r["distance"])
            logger.info(
                "ChromaDB search: query='%s' → %d/%d results within threshold %.2f",
                query[:50], len(results), len(documents), threshold,
            )
            return results

        except Exception as e:
            logger.error("ChromaDB search failed: %s", e)
            return []

    # ── Context formatting ────────────────────────────────────────────────────

    def format_context(self, results: List[Dict]) -> str:
        """
        Format search results as a plain string for injection into the planner prompt.

        Example output:
            Relevant past interactions on ubuntu@localhost:
            [1] (2026-04-20) "check disk space" → df -h
                Output: Filesystem Size Used Avail Use% ...
            [2] (2026-04-20) "list running processes" → ps aux
                Output: USER PID %CPU ...
        """
        if not results:
            return ""

        lines = [f"Relevant past interactions on {self.user_id}:"]
        for i, r in enumerate(results, start=1):
            ts      = r["timestamp"][:10] if r["timestamp"] else "unknown date"
            intent  = r["intent"][:80]
            command = r["command"][:80]
            output  = r["output"][:150].replace("\n", " ").strip()

            lines.append(f'[{i}] ({ts}) "{intent}" → {command}')
            if output:
                lines.append(f"     Output: {output}")

        return "\n".join(lines)

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def count(self) -> int:
        """Return number of stored interactions."""
        try:
            return self._get_collection().count()
        except Exception:
            return 0

    def clear(self):
        """Delete all interactions for this user (use with care)."""
        try:
            self.client.delete_collection(self.collection_name)
            logger.warning("ChromaDB: deleted collection '%s'", self.collection_name)
        except Exception as e:
            logger.error("ChromaDB clear failed: %s", e)