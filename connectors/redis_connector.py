import redis.asyncio as aioredis
import json
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import os
import logging
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class RedisClient:
    """Singleton async Redis connection."""
    _client: aioredis.Redis = None

    @classmethod
    def connect(cls):
        if cls._client is None:
            cls._client = aioredis.Redis(
                host=os.getenv("REDIS_HOST", "localhost"),
                port=int(os.getenv("REDIS_PORT", 6379)),
                decode_responses=True
            )
            logger.info("Redis connected")

    @classmethod
    async def disconnect(cls):
        if cls._client is not None:
            await cls._client.aclose()
            cls._client = None
            logger.info("Redis disconnected")

    @classmethod
    def get(cls) -> aioredis.Redis:
        if cls._client is None:
            raise RuntimeError("Redis not connected. Call RedisClient.connect() first.")
        return cls._client

    @classmethod
    async def ping(cls) -> bool:
        try:
            await cls.get().ping()
            return True
        except Exception as e:
            logger.error(f"Redis ping failed: {e}")
            return False


class SessionMemoryService:
    """
    Per-session memory for the SSH agent.

    Keyed by user_id = "username@hostname" — matching the State.user_id
    field used throughout the graph.

    Stores:
      - conversation history (sliding window list)
      - pending confirmation data (short-TTL key for CONFIRM flow)
    """

    # TTL: 3 days for conversation history, 60s for pending confirmations
    HISTORY_TTL  = int(os.getenv("SESSION_TTL_SECONDS", 259200))
    CONFIRM_TTL  = 60
    MAX_MESSAGES = 30

    def __init__(self):
        self.client = RedisClient.get()

    # ── Key helpers ───────────────────────────────────────────────

    def _history_key(self, user_id: str) -> str:
        """ssh:history:username@hostname"""
        return f"ssh:history:{user_id}"

    def _confirm_key(self, user_id: str) -> str:
        """ssh:confirm:username@hostname"""
        return f"ssh:confirm:{user_id}"

    # ── Conversation history ──────────────────────────────────────

    async def add_message(self, user_id: str, role: str, content: str, metadata: Dict = None):
        """Append a message to the session's sliding-window history."""
        key = self._history_key(user_id)
        message = {
            "role":      role,
            "content":   content,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metadata":  metadata or {}
        }
        pipe = self.client.pipeline()
        pipe.rpush(key, json.dumps(message))
        pipe.ltrim(key, -self.MAX_MESSAGES, -1)
        pipe.expire(key, self.HISTORY_TTL)
        await pipe.execute()

    async def get_history(self, user_id: str, limit: int = None) -> List[Dict]:
        """Return the most recent messages for a session."""
        key   = self._history_key(user_id)
        limit = limit or self.MAX_MESSAGES
        raw   = await self.client.lrange(key, -limit, -1)
        return [json.loads(m) for m in raw]

    async def get_context_string(self, user_id: str, limit: int = 10) -> str:
        """Return history formatted as a plain-text string for LLM injection."""
        messages = await self.get_history(user_id, limit=limit)
        if not messages:
            return ""
        return "\n".join(
            f"{msg['role'].upper()}: {msg['content']}"
            for msg in messages
        )

    async def clear_history(self, user_id: str):
        """Delete all history for a session (e.g. on disconnect)."""
        await self.client.delete(self._history_key(user_id))

    async def refresh_ttl(self, user_id: str):
        """Reset the TTL on activity so active sessions don't expire."""
        await self.client.expire(self._history_key(user_id), self.HISTORY_TTL)

    # ── Pending confirmation store ────────────────────────────────

    async def store_pending_confirm(self, user_id: str, data: Dict[str, Any]):
        """
        Store a pending confirmation payload (command + context) for 60 s.
        Called by the critic when it returns CONFIRM.
        """
        await self.client.setex(
            self._confirm_key(user_id),
            self.CONFIRM_TTL,
            json.dumps(data)
        )

    async def get_pending_confirm(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a pending confirmation, or None if expired/missing."""
        raw = await self.client.get(self._confirm_key(user_id))
        return json.loads(raw) if raw else None

    async def clear_pending_confirm(self, user_id: str):
        """Remove a pending confirmation after it has been handled."""
        await self.client.delete(self._confirm_key(user_id))
