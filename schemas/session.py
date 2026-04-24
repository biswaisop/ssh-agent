from typing import Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field
from beanie import Document

class PendingConfirmation(BaseModel):
    command_id: str
    action: str
    expires_at: datetime

class Session(Document):
    session_id: str
    user_id: str
    server_id: Optional[str] = None
    platform: str
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_active: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime
    message_count: int = 0
    pending_confirmation: Optional[PendingConfirmation] = None

    class Settings:
        name = "sessions"
        # Redis mostly handles short-term indexing, but a basic index is helpful
