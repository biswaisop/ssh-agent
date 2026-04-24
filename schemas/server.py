import pymongo
from typing import Optional, List
from datetime import datetime, timezone
from pydantic import BaseModel, Field
from beanie import Document

class ConnectionInfo(BaseModel):
    host: Optional[str] = None
    port: int = 22
    username: str = "ubuntu"
    vault_secret_path: Optional[str] = None
    last_connected_at: Optional[datetime] = None
    status: str = "connected" # connected | disconnected | error

class SandboxInfo(BaseModel):
    container_id: Optional[str] = None
    container_name: Optional[str] = None
    status: Optional[str] = None # running | stopped | null

class ServerMetadata(BaseModel):
    os: Optional[str] = "Ubuntu 22.04"
    region: Optional[str] = None
    tags: List[str] = Field(default_factory=list)

class Server(Document):
    server_id: str
    owner_id: str
    team_id: Optional[str] = None
    type: str = "byos" # managed | byos
    name: str
    description: Optional[str] = None
    connection: ConnectionInfo = Field(default_factory=ConnectionInfo)
    sandbox: SandboxInfo = Field(default_factory=SandboxInfo)
    metadata: ServerMetadata = Field(default_factory=ServerMetadata)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "servers"
        indexes = [
            pymongo.IndexModel([("server_id", pymongo.ASCENDING)], unique=True),
            pymongo.IndexModel([("owner_id", pymongo.ASCENDING)]),
            pymongo.IndexModel([("team_id", pymongo.ASCENDING)], sparse=True)
        ]

# ── API Request & Response Models ─────────────────────────────

class ServerCreateRequest(BaseModel):
    type: str = "byos"
    name: str
    host: Optional[str] = None
    port: int = 22
    username: str = "ubuntu"
    ssh_private_key: Optional[str] = None

class ServerCreateResponse(BaseModel):
    server_id: str
    name: str
    type: str
    status: str
    public_key: Optional[str] = None

class ServerResponse(BaseModel):
    server_id: str
    name: str
    type: str
    status: str
    host: Optional[str] = None
    os: Optional[str] = None
    last_connected_at: Optional[datetime] = None

class ServersListResponse(BaseModel):
    servers: List[ServerResponse]
