import pymongo
from typing import Optional
from datetime import datetime, timezone
from pydantic import BaseModel, EmailStr, Field
from beanie import Document


class Subscription(BaseModel):
    tier: str = "free" # free | pro | team
    status: str = "active" # active | cancelled | past_due
    stripe_customer_id: Optional[str] = None
    razorpay_customer_id: Optional[str] = None
    current_period_end: Optional[datetime] = None
    cancel_at_period_end: bool = False


class Usage(BaseModel):
    commands_this_month: int = 0
    commands_limit: int = 50 
    reset_date: Optional[datetime] = None
    servers_connected: int = 0
    servers_limit: int = 5


class UserSettings(BaseModel):
    default_server_id: Optional[str] = None
    confirm_destructive: bool = True
    response_verbosity: str = "normal"  # brief | normal | verbose


class User(Document):
    user_id: str
    telegram_chat_id: Optional[int] = None
    whatsapp_number: Optional[str] = None
    email: EmailStr
    name: str
    subscription: Subscription = Field(default_factory=Subscription)
    usage: Usage = Field(default_factory=Usage)
    settings: UserSettings = Field(default_factory=UserSettings)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "users"
        indexes = [
            pymongo.IndexModel([("user_id", pymongo.ASCENDING)], unique=True),
            pymongo.IndexModel([("email", pymongo.ASCENDING)], unique=True),
            pymongo.IndexModel([("telegram_chat_id", pymongo.ASCENDING)], unique=True, sparse=True),
            pymongo.IndexModel([("whatsapp_number", pymongo.ASCENDING)], unique=True, sparse=True),
        ]


# ── API Response Models ───────────────────────────────────────

class UserProfileResponse(BaseModel):
    user_id: str
    name: str
    email: EmailStr
    subscription: Subscription
    usage: Usage
