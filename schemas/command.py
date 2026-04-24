import pymongo
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from pydantic import BaseModel, Field
from beanie import Document

class CommandInput(BaseModel):
    platform: str # telegram | whatsapp | api | web
    raw_message: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class CommandRouting(BaseModel):
    agent: Optional[str] = None
    model: Optional[str] = None
    intent_score: Optional[float] = None

class ExecutionStep(BaseModel):
    step: int
    type: str # tool_call | llm_response
    tool: Optional[str] = None
    input: Optional[Dict[str, Any]] = None
    output: Optional[str] = None
    duration_ms: Optional[int] = None
    content: Optional[str] = None
    tokens_in: Optional[int] = None
    tokens_out: Optional[int] = None

class CommandExecution(BaseModel):
    steps: List[ExecutionStep] = Field(default_factory=list)
    required_confirmation: bool = False
    confirmed: bool = False
    duration_ms: Optional[int] = None

class CommandOutput(BaseModel):
    response: Optional[str] = None
    platform_message_id: Optional[str] = None

class CommandBilling(BaseModel):
    tokens_input: int = 0
    tokens_output: int = 0
    model: Optional[str] = None
    cost_usd: float = 0.0

class Command(Document):
    command_id: str
    user_id: str
    server_id: Optional[str] = None
    session_id: str
    
    input: CommandInput
    routing: CommandRouting = Field(default_factory=CommandRouting)
    execution: CommandExecution = Field(default_factory=CommandExecution)
    output: CommandOutput = Field(default_factory=CommandOutput)
    billing: CommandBilling = Field(default_factory=CommandBilling)
    
    status: str = "pending" # pending | running | completed | failed | blocked
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None

    class Settings:
        name = "commands"
        indexes = [
            pymongo.IndexModel([("command_id", pymongo.ASCENDING)], unique=True),
            pymongo.IndexModel([("user_id", pymongo.ASCENDING), ("created_at", pymongo.DESCENDING)]),
            pymongo.IndexModel([("server_id", pymongo.ASCENDING), ("created_at", pymongo.DESCENDING)]),
            pymongo.IndexModel([("session_id", pymongo.ASCENDING)]),
            pymongo.IndexModel([("status", pymongo.ASCENDING)]),
        ]

# ── API Request & Response Models ─────────────────────────────

class AgentRunRequest(BaseModel):
    message: str
    server_id: str
    session_id: Optional[str] = None
    confirmed: bool = False

class AgentRunAcceptedResponse(BaseModel):
    command_id: str
    session_id: str
    status: str = "queued"
    trace_url: str

class CommandStatusResponse(BaseModel):
    command_id: str
    status: str
    response: Optional[str] = None
    steps: List[ExecutionStep] = Field(default_factory=list)
    duration_ms: Optional[int] = None
    tokens_used: Optional[int] = None

class CommandHistoryItem(BaseModel):
    command_id: str
    input_message: str
    response: Optional[str] = None
    agent: Optional[str] = None
    status: str
    created_at: datetime
    duration_ms: Optional[int] = None

class CommandHistoryResponse(BaseModel):
    total: int
    items: List[CommandHistoryItem]
