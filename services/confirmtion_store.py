"""
Thin async wrappers around SessionMemoryService for the confirmation flow.

These replace the old sync confirmation_store.py which was broken —
it called RedisClient.get() at module import time (before connect())
and used blocking setex/get/delete on an async redis client.

Usage:
    from services.confirmation_store import store_pending, get_pending, clear_pending
"""
from connectors.redis_connector import SessionMemoryService

_svc = SessionMemoryService()


async def store_pending(user_id: str, data: dict):
    await _svc.store_pending_confirm(user_id, data)


async def get_pending(user_id: str) -> dict | None:
    return await _svc.get_pending_confirm(user_id)


async def clear_pending(user_id: str):
    await _svc.clear_pending_confirm(user_id)