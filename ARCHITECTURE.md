# GenOS — Complete Architecture Document

> Natural language OS control via AI agents, accessible over WhatsApp and Telegram.  
> Version 1.0 — Hackathon + Scale Reference

---

## Table of Contents

1. [Vision and Core Concept](#1-vision-and-core-concept)
2. [System Overview](#2-system-overview)
3. [Tech Stack](#3-tech-stack)
4. [Environment Variables](#4-environment-variables)
5. [Docker Image Design](#5-docker-image-design)
6. [Project Structure](#6-project-structure)
7. [Database Design](#7-database-design)
8. [API Reference](#8-api-reference)
9. [Agent Architecture](#9-agent-architecture)
10. [OS Control Layer](#10-os-control-layer)
11. [Memory System](#11-memory-system)
12. [Multi-Tenant Design](#12-multi-tenant-design)
13. [Messaging Interfaces](#13-messaging-interfaces)
14. [Request Lifecycle](#14-request-lifecycle)
15. [Security Model](#15-security-model)
16. [Packaging and Deployment](#16-packaging-and-deployment)
17. [Scaling Playbook](#17-scaling-playbook)

---

## 1. Vision and Core Concept

GenOS is a multi-tenant AI operating system that lets users control a Linux environment using plain English, delivered through WhatsApp and Telegram. It is **not a chatbot** — it is an agent runtime that acts on real infrastructure.

### The three-layer model

```
User (natural language)
        ↓
Agent Kernel (orchestration, routing, memory)
        ↓
OS Control Layer (shell, files, processes, screen, network)
        ↓
Ubuntu Sandbox / User's own VPS
```

### Two server modes

| Mode | Description | Who it's for |
|------|-------------|--------------|
| **Managed** | GenOS spins up a Docker Ubuntu container per user | Free tier, demos, users without a VPS |
| **BYOS** | User connects their own VPS via SSH key | Pro + Team tier, production use |

---

## 2. System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        INTERFACE LAYER                          │
│   WhatsApp (Twilio)          Telegram Bot          Web UI       │
└────────────────┬────────────────────┬────────────────┬──────────┘
                 │                    │                │
                 ▼                    ▼                ▼
┌─────────────────────────────────────────────────────────────────┐
│                        API GATEWAY (FastAPI)                    │
│   /webhook/telegram    /webhook/whatsapp    /api/v1/*           │
│   Auth middleware      Rate limiting        WebSocket /ws/trace │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                        TASK QUEUE (Redis Streams)               │
│         Messages enqueued here, workers consume async           │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                        AGENT KERNEL (LangGraph)                 │
│                                                                 │
│   Orchestrator ──► Shell Agent    ──► Shell Tools               │
│                ──► File Agent     ──► File Tools                │
│                ──► Process Agent  ──► Process Tools             │
│                ──► Screen Agent   ──► Screen Tools              │
│                ──► Network Agent  ──► Network Tools             │
│                ──► Multi Agent    ──► All Tools                 │
│                                                                 │
│   Critic Agent (safety check before any destructive action)     │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                  ┌────────────┴────────────┐
                  ▼                         ▼
┌─────────────────────────┐   ┌─────────────────────────────────┐
│   MANAGED SANDBOX       │   │   BYOS (User's Own VPS)         │
│   Docker Ubuntu 22.04   │   │   SSH via Paramiko              │
│   Xvfb virtual display  │   │   Scoped keypair per user       │
│   Isolated per user     │   │   Edge runner (Fly.io region)   │
└─────────────────────────┘   └─────────────────────────────────┘
                  │
      ┌───────────┼───────────┐
      ▼           ▼           ▼
   MongoDB      Redis       Qdrant
   (storage)   (sessions)  (memory)
```

---

## 3. Tech Stack

### Backend

| Component | Technology | Why |
|-----------|------------|-----|
| API framework | FastAPI 0.115 + Python 3.11 | Async, matches AI libraries, you know it |
| Agent framework | LangGraph 0.2 | Stateful multi-agent graphs with conditional routing |
| LLM (complex) | Claude Sonnet 4.5 | Orchestration, reasoning, debugging |
| LLM (simple) | Claude Haiku 4.5 | Cheap commands — list files, check CPU |
| LLM (vision) | Claude Sonnet 4.5 vision | Screen agent — reads Xvfb screenshot |
| Embeddings | biswaisop/embedding-service | Your own microservice, zero API cost |
| SSH execution | Paramiko | BYOS connector into user's VPS |
| Container control | Docker SDK for Python | Managed sandbox execution |
| Task queue | Celery + Redis Streams | Async agent execution, horizontal scale |
| Session memory | Redis 7 | Per-user conversation context, TTL 24h |
| Primary DB | MongoDB Atlas + Motor | Flexible schema, async driver |
| Vector store | Qdrant Cloud | Per-user server memory, multi-tenant isolation |
| Secret storage | HashiCorp Vault | SSH keypairs encrypted at rest |

### Frontend

| Component | Technology | Why |
|-----------|------------|-----|
| Framework | Next.js 14 + TypeScript | App router, SSR landing, client dashboard |
| Styling | Tailwind CSS + shadcn/ui | Production components fast |
| Auth | Clerk | GitHub/Google OAuth in 30 minutes |
| Live trace | WebSocket (FastAPI) | Real-time agent decision stream |
| Payments | Stripe + Razorpay | Global (USD) + India (UPI) |

### Messaging

| Platform | Library | Notes |
|----------|---------|-------|
| Telegram | python-telegram-bot v20 | Async, webhook mode |
| WhatsApp MVP | Twilio Sandbox | Free, no Meta approval |
| WhatsApp Prod | WhatsApp Business API | Apply post-launch, 4–6 weeks |

### Infrastructure

| Component | MVP | Production |
|-----------|-----|-----------|
| API hosting | Railway | Fly.io + Hetzner |
| Frontend | Vercel | Vercel |
| Containers | Docker Compose | k3s (lightweight k8s) |
| Edge runners | — | Fly.io multi-region |
| CI/CD | GitHub Actions | GitHub Actions |
| Tunnel (dev) | ngrok | — |
| Logs | structlog + Axiom | structlog + Axiom |
| Errors | Sentry | Sentry |
| Metrics | — | Prometheus + Grafana |

---

## 4. Environment Variables

### API service `.env`

```env
# ── LLM ───────────────────────────────────────────────────────
ANTHROPIC_API_KEY=sk-ant-...

# ── Messaging ─────────────────────────────────────────────────
TELEGRAM_TOKEN=...                         # from @BotFather
TWILIO_ACCOUNT_SID=...
TWILIO_AUTH_TOKEN=...
TWILIO_WHATSAPP_FROM=whatsapp:+14155238886 # Twilio sandbox number

# ── Databases ─────────────────────────────────────────────────
MONGO_URL=mongodb+srv://user:pass@cluster.mongodb.net/GenOS
REDIS_URL=redis://localhost:6379/0
QDRANT_URL=https://your-cluster.qdrant.io
QDRANT_API_KEY=...

# ── Embedding service ─────────────────────────────────────────
EMBEDDING_SERVICE_URL=http://localhost:8001  # biswaisop/embedding-service

# ── Auth ──────────────────────────────────────────────────────
CLERK_SECRET_KEY=sk_...
CLERK_PUBLISHABLE_KEY=pk_...
JWT_SECRET=...                             # for internal service auth

# ── Sandbox ───────────────────────────────────────────────────
SANDBOX_CONTAINER_PREFIX=GenOS_sandbox_  # containers named {prefix}{user_id}
SANDBOX_WORKSPACE=/workspace
DOCKER_SOCKET=/var/run/docker.sock

# ── Secret storage ────────────────────────────────────────────
VAULT_ADDR=http://vault:8200
VAULT_TOKEN=...                            # or use AppRole in prod

# ── Payments ──────────────────────────────────────────────────
STRIPE_SECRET_KEY=sk_...
STRIPE_WEBHOOK_SECRET=whsec_...
RAZORPAY_KEY_ID=...
RAZORPAY_KEY_SECRET=...

# ── Observability ─────────────────────────────────────────────
SENTRY_DSN=https://...@sentry.io/...
AXIOM_TOKEN=...
AXIOM_DATASET=GenOS-logs

# ── App config ────────────────────────────────────────────────
ENVIRONMENT=development                    # development | production
LOG_LEVEL=INFO
ALLOWED_ORIGINS=http://localhost:3000,https://yourdomain.com
FREE_TIER_COMMAND_LIMIT=50                 # commands per month
AGENT_TIMEOUT_SECONDS=120
```

### Frontend `.env.local`

```env
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_...
CLERK_SECRET_KEY=sk_...
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000
NEXT_PUBLIC_RAZORPAY_KEY_ID=...
STRIPE_SECRET_KEY=sk_...
```

---

## 5. Docker Image Design

### Two images — understand the distinction

| Image | Purpose | What's in it |
|-------|---------|-------------|
| `GenOS-api` | Runs FastAPI, agents, Celery workers | Python, dependencies, no system tools |
| `GenOS-sandbox` | The Ubuntu environment agents control | Full Linux toolset, Xvfb, GUI stack |

---

### `GenOS-sandbox` — Ubuntu control environment

This is the image that gets **executed by agents**. It needs every tool agents might call.

```dockerfile
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV DISPLAY=:99

# System tools agents will use
RUN apt-get update && apt-get install -y \
    # Shell + scripting
    bash curl wget git vim nano unzip zip tar \
    # Process management
    htop procps psutil \
    # File search
    ripgrep findutils \
    # Network tools
    nmap netcat-openbsd dnsutils iputils-ping \
    # GUI + virtual display (screen agent)
    xvfb x11vnc scrot xdotool wmctrl \
    # Python runtime (for running user scripts)
    python3.11 python3-pip python3-venv \
    # Node.js (for running JS scripts)
    nodejs npm \
    # Cron
    cron \
    # Chromium (for screen agent browser control)
    chromium-browser \
    && rm -rf /var/lib/apt/lists/*

# Python packages available inside sandbox
RUN pip3 install psutil requests httpx pandas numpy

WORKDIR /workspace

# Startup: launch Xvfb virtual display
CMD ["bash", "-c", "Xvfb :99 -screen 0 1280x720x24 & tail -f /dev/null"]
```

**What NOT to put in the sandbox image:**
- Your API code — it lives in `GenOS-api`
- LangGraph / LangChain — not needed inside the sandbox
- Your `.env` file — never bake secrets into images
- MongoDB / Redis — these are separate services
- Large ML models — served by your embedding microservice separately

---

### `GenOS-api` — FastAPI application

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Only what the API needs
RUN apt-get update && apt-get install -y \
    docker.io \          # Docker CLI to exec into sandbox
    openssh-client \     # SSH for BYOS connector
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

---

### `docker-compose.yml` — full local stack

```yaml
version: "3.9"

services:
  sandbox:
    build:
      context: ./sandbox
      dockerfile: Dockerfile.sandbox
    container_name: GenOS_sandbox_default
    environment:
      - DISPLAY=:99
    volumes:
      - sandbox_workspace:/workspace
    networks:
      - GenOS_net
    restart: unless-stopped

  api:
    build:
      context: ./api
    container_name: GenOS_api
    ports:
      - "8000:8000"
    env_file: .env
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
    networks:
      - GenOS_net
    depends_on: [redis, mongo, sandbox]
    restart: unless-stopped

  worker:
    build:
      context: ./api
    container_name: GenOS_worker
    command: celery -A tasks worker --loglevel=info --concurrency=4
    env_file: .env
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
    networks:
      - GenOS_net
    depends_on: [redis, mongo]
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    container_name: GenOS_redis
    networks:
      - GenOS_net
    restart: unless-stopped

  mongo:
    image: mongo:7
    container_name: GenOS_mongo
    environment:
      MONGO_INITDB_DATABASE: GenOS
    volumes:
      - mongo_data:/data/db
    networks:
      - GenOS_net
    restart: unless-stopped

volumes:
  sandbox_workspace:
  mongo_data:

networks:
  GenOS_net:
    driver: bridge
```

---

## 6. Project Structure

```
GenOS/
├── .env                          # secrets — never commit
├── .env.example                  # template for new devs
├── docker-compose.yml
├── sandbox/
│   └── Dockerfile.sandbox        # Ubuntu control environment image
│
└── api/
    ├── Dockerfile
    ├── requirements.txt
    ├── main.py                   # FastAPI app, router registration
    ├── config.py                 # Settings from env vars (pydantic-settings)
    ├── tasks.py                  # Celery app + task definitions
    │
    ├── routers/
    │   ├── webhooks.py           # /webhook/telegram, /webhook/whatsapp
    │   ├── agents.py             # /api/v1/agent/*
    │   ├── servers.py            # /api/v1/servers/*
    │   ├── users.py              # /api/v1/users/*
    │   ├── payments.py           # /api/v1/payments/*
    │   └── ws.py                 # WebSocket /ws/trace/{session_id}
    │
    ├── agents/
    │   ├── graph.py              # LangGraph StateGraph definition
    │   ├── orchestrator.py       # Intent routing node
    │   ├── critic.py             # Safety check node
    │   ├── shell_agent.py        # Shell execution agent
    │   ├── file_agent.py         # File management agent
    │   ├── process_agent.py      # Process monitoring agent
    │   ├── screen_agent.py       # Screenshot + GUI agent
    │   ├── network_agent.py      # Network operations agent
    │   └── multi_agent.py        # Complex multi-step agent
    │
    ├── tools/
    │   ├── os_tools.py           # All @tool functions (docker exec / SSH)
    │   ├── shell_tools.py
    │   ├── file_tools.py
    │   ├── process_tools.py
    │   ├── screen_tools.py
    │   └── network_tools.py
    │
    ├── connectors/
    │   ├── sandbox.py            # Docker SDK — manages Ubuntu containers
    │   └── ssh.py                # Paramiko — connects to user's own VPS
    │
    ├── memory/
    │   ├── session.py            # Redis — short-term conversation context
    │   └── vector.py             # Qdrant — long-term server memory
    │
    ├── models/
    │   ├── user.py               # Pydantic + Beanie document models
    │   ├── server.py
    │   ├── command.py
    │   └── session.py
    │
    ├── middleware/
    │   ├── auth.py               # Clerk JWT verification
    │   └── ratelimit.py          # Per-user command rate limiting
    │
    └── services/
        ├── messaging.py          # Telegram + WhatsApp send helpers
        ├── billing.py            # Stripe + Razorpay abstraction
        └── metrics.py            # Prometheus counters + histograms
```

---

## 7. Database Design

### MongoDB — primary data store

Uses **Beanie ODM** for async document access with Pydantic models.

---

#### Collection: `users`

Stores user account, subscription, and platform identifiers.

```json
{
  "_id": "ObjectId",
  "user_id": "clerk_user_abc123",          // Clerk user ID — primary identifier
  "telegram_chat_id": 123456789,           // null if not connected
  "whatsapp_number": "+919876543210",      // null if not connected
  "email": "user@example.com",
  "name": "biswa",
  "subscription": {
    "tier": "pro",                         // free | pro | team
    "status": "active",                   // active | cancelled | past_due
    "stripe_customer_id": "cus_abc",      // null for Razorpay users
    "razorpay_customer_id": "cust_abc",   // null for Stripe users
    "current_period_end": "2025-10-01T00:00:00Z",
    "cancel_at_period_end": false
  },
  "usage": {
    "commands_this_month": 23,
    "commands_limit": 50,                  // 50 free, unlimited pro/team
    "reset_date": "2025-09-01T00:00:00Z"
  },
  "settings": {
    "default_server_id": "ObjectId",
    "confirm_destructive": true,           // always ask before rm/kill
    "response_verbosity": "normal"        // brief | normal | verbose
  },
  "created_at": "2025-08-01T10:00:00Z",
  "updated_at": "2025-08-15T14:22:00Z"
}
```

**Indexes:**
```
user_id         unique
telegram_chat_id  sparse unique
whatsapp_number   sparse unique
email           unique
```

---

#### Collection: `servers`

One document per server connection (managed sandbox or user's VPS).

```json
{
  "_id": "ObjectId",
  "server_id": "srv_abc123",              // stable public ID
  "owner_id": "clerk_user_abc123",        // foreign key → users.user_id
  "team_id": null,                        // set for Team tier shared servers

  "type": "byos",                         // managed | byos
  "name": "My DigitalOcean droplet",
  "description": "Production server",

  "connection": {
    "host": "1.2.3.4",                    // null for managed
    "port": 22,
    "username": "ubuntu",
    "vault_secret_path": "secret/users/abc123/srv_abc123",  // SSH key in Vault
    "last_connected_at": "2025-08-20T09:00:00Z",
    "status": "connected"                 // connected | disconnected | error
  },

  "sandbox": {
    "container_id": null,                 // set for managed type
    "container_name": null,
    "status": null                        // running | stopped | null
  },

  "metadata": {
    "os": "Ubuntu 22.04",
    "region": "blr1",                     // DigitalOcean Bangalore
    "tags": ["production", "api"]
  },

  "created_at": "2025-08-01T10:00:00Z",
  "updated_at": "2025-08-20T09:00:00Z"
}
```

**Indexes:**
```
server_id       unique
owner_id        (for listing user's servers)
team_id         sparse (for team shared access)
```

---

#### Collection: `commands`

Immutable audit log of every agent interaction. Append-only.

```json
{
  "_id": "ObjectId",
  "command_id": "cmd_xyz789",
  "user_id": "clerk_user_abc123",
  "server_id": "srv_abc123",
  "session_id": "sess_abc",              // groups commands in one conversation

  "input": {
    "platform": "telegram",             // telegram | whatsapp | api | web
    "raw_message": "what's eating my CPU?",
    "timestamp": "2025-08-20T09:05:00Z"
  },

  "routing": {
    "agent": "process_agent",           // which agent handled it
    "model": "claude-haiku-4-5",        // which LLM was used
    "intent_score": 0.94                // orchestrator confidence
  },

  "execution": {
    "steps": [                          // agent trace — each tool call
      {
        "step": 1,
        "type": "tool_call",
        "tool": "list_processes",
        "input": {},
        "output": "PID   CPU%  CMD\n1234  67.2  chromium...",
        "duration_ms": 340
      },
      {
        "step": 2,
        "type": "llm_response",
        "content": "Chromium is using 67% CPU. Want me to kill it?",
        "tokens_in": 412,
        "tokens_out": 28
      }
    ],
    "required_confirmation": true,
    "confirmed": true,
    "duration_ms": 1820
  },

  "output": {
    "response": "Killed chromium. CPU is now at 12%.",
    "platform_message_id": "tg_msg_456"
  },

  "billing": {
    "tokens_input": 412,
    "tokens_output": 28,
    "model": "claude-haiku-4-5",
    "cost_usd": 0.000052
  },

  "status": "completed",               // pending | running | completed | failed | blocked
  "created_at": "2025-08-20T09:05:00Z",
  "completed_at": "2025-08-20T09:05:02Z"
}
```

**Indexes:**
```
user_id + created_at    (paginated history queries)
server_id + created_at  (per-server audit log)
session_id              (grouping by conversation)
status                  (finding pending/running)
command_id              unique
```

---

#### Collection: `sessions`

Tracks active conversation sessions — bridges multiple messages in one "context window."

```json
{
  "_id": "ObjectId",
  "session_id": "sess_abc",
  "user_id": "clerk_user_abc123",
  "server_id": "srv_abc123",
  "platform": "telegram",
  "started_at": "2025-08-20T09:00:00Z",
  "last_active": "2025-08-20T09:10:00Z",
  "expires_at": "2025-08-20T21:00:00Z",  // TTL 12h of inactivity
  "message_count": 7,
  "pending_confirmation": {
    "command_id": "cmd_xyz789",
    "action": "kill chromium",
    "expires_at": "2025-08-20T09:06:00Z"  // confirm within 60s
  }
}
```

---

### Redis — session and queue layer

All Redis keys are namespaced by `user:{user_id}:*` for multi-tenant isolation.

```
# Short-term conversation memory (LangGraph checkpointer)
user:{user_id}:session:{session_id}:messages    → JSON list of messages, TTL 24h
user:{user_id}:session:{session_id}:state       → LangGraph AgentState, TTL 24h

# Pending confirmations (dangerous command awaiting user yes/no)
user:{user_id}:pending_confirm                  → {command_id, action, expires_at}, TTL 60s

# Rate limiting (free tier command counter)
user:{user_id}:cmd_count:{YYYY-MM}             → integer, TTL until month end

# Active server connection per user (which server is "selected")
user:{user_id}:active_server                   → server_id, TTL 7 days

# WebSocket trace stream (live agent trace for web dashboard)
stream:trace:{session_id}                      → Redis Stream, TTL 1h

# Task state (Celery result backend)
celery-task-meta-{task_id}                     → task result, TTL 24h
```

---

### Qdrant — vector memory (long-term server knowledge)

One collection per user: `user_{user_id}_memory`

Each point represents something the agent learned about the user's server:

```json
{
  "id": "uuid",
  "vector": [0.12, -0.34, ...],          // 768-dim from your embedding service
  "payload": {
    "user_id": "clerk_user_abc123",
    "server_id": "srv_abc123",
    "type": "observation",               // observation | preference | fact
    "content": "nginx uses port 443 and crashes when memory exceeds 2GB",
    "context": "User asked about slow response times 3 times this week",
    "importance": 0.87,                  // 0.0–1.0, used for retrieval ranking
    "created_at": "2025-08-15T10:00:00Z",
    "access_count": 4
  }
}
```

**Retrieval strategy:** before each agent run, embed the user's message and retrieve top-5 most similar memories for that server. Inject into the system prompt as context.

---

## 8. API Reference

Base URL: `https://api.GenOS.dev`  
Auth: `Authorization: Bearer {clerk_jwt}` on all `/api/v1/*` routes  
Content-Type: `application/json`

---

### Webhooks (no auth — validated by platform signature)

#### `POST /webhook/telegram`

Receives Telegram updates. Validates bot token. Enqueues to Redis Streams.

**Request** (Telegram sends this automatically):
```json
{
  "update_id": 123456,
  "message": {
    "chat": { "id": 987654321 },
    "from": { "id": 111222333, "username": "biswa" },
    "text": "what's eating my CPU?",
    "date": 1724140800
  }
}
```

**Response:**
```json
{ "ok": true }
```

**Status codes:**
| Code | Meaning |
|------|---------|
| 200 | Message accepted and enqueued |
| 400 | Invalid update format |
| 403 | Token mismatch |

---

#### `POST /webhook/whatsapp`

Receives Twilio WhatsApp form-encoded POST.

**Request** (form-encoded):
```
From=whatsapp%3A%2B919876543210
Body=what%27s+eating+my+CPU%3F
MessageSid=SM123abc
```

**Response:**
```json
{ "status": "queued" }
```

**Status codes:**
| Code | Meaning |
|------|---------|
| 200 | Message accepted |
| 400 | Missing required fields |

---

### Agent API

#### `POST /api/v1/agent/run`

Run an agent command directly (web dashboard or API consumers).

**Request:**
```json
{
  "message": "find all python files modified today and zip them",
  "server_id": "srv_abc123",
  "session_id": "sess_abc",           // optional, creates new if omitted
  "confirmed": false                  // true if user confirmed a dangerous op
}
```

**Response `202 Accepted`:**
```json
{
  "command_id": "cmd_xyz789",
  "session_id": "sess_abc",
  "status": "queued",
  "trace_url": "ws://api.GenOS.dev/ws/trace/sess_abc"
}
```

**Status codes:**
| Code | Meaning |
|------|---------|
| 202 | Command queued, track via WebSocket |
| 400 | Invalid request body |
| 401 | Unauthenticated |
| 403 | Server not owned by user |
| 402 | Command limit exceeded (free tier) |
| 429 | Rate limited |
| 500 | Internal error |

---

#### `GET /api/v1/agent/status/{command_id}`

Poll command status if not using WebSocket.

**Response `200`:**
```json
{
  "command_id": "cmd_xyz789",
  "status": "completed",
  "response": "Found 7 .py files. Zipped to /workspace/output.zip",
  "steps": [
    {
      "step": 1,
      "tool": "search_files",
      "input": { "pattern": "*.py" },
      "output": "file1.py\nfile2.py...",
      "duration_ms": 240
    }
  ],
  "duration_ms": 1820,
  "tokens_used": 440
}
```

**Status codes:**
| Code | Meaning |
|------|---------|
| 200 | Command found |
| 404 | Command not found |
| 403 | Not your command |

---

#### `GET /api/v1/agent/history`

Paginated command history for the authenticated user.

**Query params:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `server_id` | string | — | Filter by server |
| `limit` | int | 20 | Results per page |
| `skip` | int | 0 | Offset |
| `status` | string | — | Filter: completed\|failed\|blocked |

**Response `200`:**
```json
{
  "total": 127,
  "items": [
    {
      "command_id": "cmd_xyz789",
      "input_message": "what's eating my CPU?",
      "response": "Chromium was using 67% CPU. Killed it.",
      "agent": "process_agent",
      "status": "completed",
      "created_at": "2025-08-20T09:05:00Z",
      "duration_ms": 1820
    }
  ]
}
```

---

### Servers API

#### `GET /api/v1/servers`

List all servers owned by the authenticated user.

**Response `200`:**
```json
{
  "servers": [
    {
      "server_id": "srv_abc123",
      "name": "My DigitalOcean droplet",
      "type": "byos",
      "status": "connected",
      "host": "1.2.3.4",
      "os": "Ubuntu 22.04",
      "last_connected_at": "2025-08-20T09:00:00Z"
    }
  ]
}
```

---

#### `POST /api/v1/servers`

Add a new server (BYOS or request managed sandbox).

**Request:**
```json
{
  "type": "byos",
  "name": "My VPS",
  "host": "1.2.3.4",
  "port": 22,
  "username": "ubuntu",
  "ssh_private_key": "-----BEGIN OPENSSH PRIVATE KEY-----\n..."
}
```

> SSH private key is immediately stored in Vault. Never persisted in MongoDB.

**Response `201`:**
```json
{
  "server_id": "srv_newxyz",
  "name": "My VPS",
  "type": "byos",
  "status": "connecting",
  "public_key": "ssh-ed25519 AAAA... GenOS@agent"
}
```

**Status codes:**
| Code | Meaning |
|------|---------|
| 201 | Server added, connection test started |
| 400 | Invalid SSH key format or missing fields |
| 402 | Server limit reached for current tier |
| 409 | Server with this host already exists |

---

#### `DELETE /api/v1/servers/{server_id}`

Remove a server connection. Destroys managed sandbox if applicable.

**Response `200`:**
```json
{ "deleted": true, "server_id": "srv_abc123" }
```

---

#### `GET /api/v1/servers/{server_id}/metrics`

Live system metrics from a connected server.

**Response `200`:**
```json
{
  "server_id": "srv_abc123",
  "timestamp": "2025-08-20T09:10:00Z",
  "cpu": {
    "usage_percent": 23.4,
    "load_avg": [0.8, 1.2, 1.1]
  },
  "memory": {
    "total_gb": 4.0,
    "used_gb": 2.1,
    "free_gb": 1.9,
    "usage_percent": 52.5
  },
  "disk": {
    "total_gb": 50.0,
    "used_gb": 12.3,
    "free_gb": 37.7,
    "usage_percent": 24.6
  },
  "network": {
    "bytes_sent": 1024000,
    "bytes_recv": 2048000
  },
  "top_processes": [
    { "pid": 1234, "name": "nginx", "cpu_percent": 2.1, "mem_mb": 45.2 }
  ]
}
```

---

### Users API

#### `GET /api/v1/users/me`

Get current user profile and usage.

**Response `200`:**
```json
{
  "user_id": "clerk_user_abc123",
  "name": "biswa",
  "email": "biswa@example.com",
  "subscription": {
    "tier": "pro",
    "status": "active",
    "current_period_end": "2025-09-01T00:00:00Z"
  },
  "usage": {
    "commands_this_month": 23,
    "commands_limit": -1,
    "servers_connected": 2,
    "servers_limit": 5
  }
}
```

---

### Payments API

#### `POST /api/v1/payments/create-checkout`

Create a Stripe or Razorpay checkout session.

**Request:**
```json
{
  "tier": "pro",
  "billing_period": "monthly",
  "currency": "inr",                   // usd | inr
  "success_url": "https://app.GenOS.dev/dashboard?upgraded=true",
  "cancel_url": "https://app.GenOS.dev/pricing"
}
```

**Response `200`:**
```json
{
  "provider": "razorpay",
  "checkout_url": "https://rzp.io/l/abc",
  "session_id": "pay_abc123"
}
```

---

#### `POST /api/v1/payments/webhook/stripe`

Stripe webhook handler. Verifies signature, updates subscription status.

#### `POST /api/v1/payments/webhook/razorpay`

Razorpay webhook handler.

---

### WebSocket

#### `WS /ws/trace/{session_id}`

Live agent execution trace stream. Connect immediately after POSTing to `/api/v1/agent/run`.

**Messages received (server → client):**

```json
// Agent started
{ "type": "agent_start", "agent": "process_agent", "timestamp": "..." }

// Tool being called
{ "type": "tool_call", "tool": "list_processes", "input": {}, "step": 1 }

// Tool result
{ "type": "tool_result", "output": "PID  CPU%  CMD\n1234 67.2 chromium", "step": 1 }

// LLM thinking
{ "type": "llm_token", "token": "Chromium" }

// Confirmation required
{ "type": "confirmation_required", "action": "kill chromium", "command_id": "cmd_xyz" }

// Final response
{ "type": "complete", "response": "Killed chromium. CPU now at 12%.", "duration_ms": 1820 }

// Error
{ "type": "error", "message": "SSH connection refused", "code": "SSH_REFUSED" }
```

---

## 9. Agent Architecture

### LangGraph StateGraph

```python
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    user_id: str
    server_id: str
    session_id: str
    next_agent: str           # routing decision
    confirmed: bool           # user confirmed dangerous op
    server_memory: list       # injected from Qdrant before graph runs
    command_id: str           # for WebSocket trace updates
```

### Graph topology

```
START
  │
  ▼
orchestrator ──────────────────────────────────────────┐
  │ (conditional edge based on next_agent)             │
  ├──► shell_agent   ──► shell_tools   ──► shell_agent │
  ├──► file_agent    ──► file_tools    ──► file_agent  │
  ├──► process_agent ──► process_tools ──► process_agent│
  ├──► screen_agent  ──► screen_tools  ──► screen_agent │
  ├──► network_agent ──► network_tools ──► network_agent│
  └──► multi_agent   ──► all_tools     ──► multi_agent  │
                                                        │
  Each agent loops: agent → tools → agent (until done) │
  Then routes to critic for safety check               │
                                                        │
critic ─────────────────────────────────────────────────┘
  │
  ├── SAFE     → END (response sent to user)
  ├── CONFIRM  → END (confirmation message sent, await user reply)
  └── BLOCK    → END (blocked message sent)
```

### Orchestrator intent routing

The orchestrator receives the raw user message and outputs a single agent name. Uses `claude-haiku-4-5` (cheap, fast, zero reasoning needed).

**Intent → Agent mapping:**

| Intent examples | Routes to |
|----------------|-----------|
| run script, execute command, install package | `shell_agent` |
| read file, write file, find files, zip, delete | `file_agent` |
| CPU usage, memory, kill process, list processes, cron | `process_agent` |
| screenshot, open app, click, type, see screen | `screen_agent` |
| ping, fetch URL, port scan, network check | `network_agent` |
| multi-step, complex, combining multiple operations | `multi_agent` |

### Critic safety rules

Before any tool that modifies the system runs, the critic checks:

```
BLOCK  → rm -rf /, format disk, dd, system shutdown, delete outside /workspace
CONFIRM → rm, pkill, kill, systemctl stop, apt remove, any delete operation
SAFE   → read operations, list, cat, ps, top, ping, curl, python -c
```

---

## 10. OS Control Layer

### How agents execute commands

**Managed sandbox** — via Docker SDK:
```python
import docker
client = docker.from_env()
container = client.containers.get(f"GenOS_sandbox_{user_id}")
result = container.exec_run(["bash", "-c", command], stream=True)
```

**BYOS** — via Paramiko SSH:
```python
import paramiko
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
# Private key fetched from Vault, never from disk
key = paramiko.RSAKey.from_private_key(io.StringIO(vault_secret))
ssh.connect(hostname=host, port=port, username=username, pkey=key)
stdin, stdout, stderr = ssh.exec_command(command)
```

Both connectors implement the same interface (`BaseConnector`) so agents are agnostic to which one runs.

### System metrics collection

The process agent calls `get_system_stats` which runs:

```bash
# CPU
top -bn1 | grep "Cpu(s)"

# Memory
free -h

# Disk
df -h /workspace

# Processes
ps aux --sort=-%cpu | head -20

# Network
cat /proc/net/dev
```

Output is parsed by the LLM into structured natural language.

### Screen agent (Xvfb)

The sandbox runs a virtual display via Xvfb on `:99`. The screen agent:

1. Calls `take_screenshot` → runs `scrot /tmp/screenshot.png` inside container
2. Copies PNG out via `docker cp`
3. Encodes to base64, sends to Claude Sonnet vision
4. Claude describes what's on screen and decides next action
5. Uses `xdotool` + `wmctrl` to click, type, resize windows

---

## 11. Memory System

### Two-tier memory architecture

```
SHORT-TERM (Redis)                    LONG-TERM (Qdrant)
──────────────────────                ──────────────────────
Per session                           Per user + server
24h TTL                               Permanent
LangGraph messages list               Semantic vector search
Fast (sub-millisecond)                Slower (5–20ms)
Conversation context                  Server knowledge
```

### How memory flows through a request

```
1. User sends message
2. Load session messages from Redis (last N turns)
3. Embed user message via embedding-service
4. Query Qdrant for top-5 relevant server memories
5. Inject memories into agent system prompt:
   "Known facts about this server: [memories]"
6. Run agent graph (messages + memories in context)
7. Agent completes, response sent to user
8. Save new messages to Redis session
9. Extract any new facts from the interaction
10. Store new facts as vectors in Qdrant
```

### Memory extraction

After each successful command, the agent extracts learnable facts:

```
Command: "nginx keeps crashing when load exceeds 500 req/s"
Extracted memory: "nginx crashes above 500 req/s — likely worker_processes config issue"
Stored in Qdrant with server_id tag
```

Next time user asks "why is my site slow?", this memory surfaces automatically.

---

## 12. Multi-Tenant Design

### Isolation guarantees

Every layer enforces user-level isolation:

| Layer | Isolation mechanism |
|-------|-------------------|
| API | Clerk JWT → `user_id` extracted, all queries filtered by it |
| MongoDB | Every document has `owner_id`, all queries include `{owner_id: user_id}` |
| Redis | All keys namespaced `user:{user_id}:*` |
| Qdrant | Separate collection per user: `user_{user_id}_memory` |
| Docker sandbox | Separate container per user: `GenOS_sandbox_{user_id}` |
| SSH | Separate keypair per user per server, stored in Vault at `secret/users/{user_id}/{server_id}` |

### Tier enforcement

Every agent run checks limits before executing:

```python
async def check_limits(user_id: str, tier: str) -> None:
    if tier == "free":
        count = await redis.get(f"user:{user_id}:cmd_count:{month}")
        if int(count or 0) >= FREE_TIER_COMMAND_LIMIT:
            raise HTTPException(402, "Monthly command limit reached. Upgrade to Pro.")
    # Pro and Team: no limit
```

### Managed sandbox lifecycle

| Event | Action |
|-------|--------|
| User signs up (free) | Sandbox container created on first command |
| User idle 30 min | Container stopped (resources reclaimed) |
| User sends message | Container started (cold start ~2s) |
| User deletes account | Container + volume destroyed |
| Pro user | Container kept running (warm, instant response) |

---

## 13. Messaging Interfaces

### Telegram message flow

```
1. User sends message to @GenOSBot
2. Telegram POST to /webhook/telegram
3. FastAPI validates bot token
4. Extracts: chat_id, user message, telegram user id
5. Looks up user by telegram_chat_id in MongoDB
6. If new user: creates account, sends welcome + server setup instructions
7. Checks pending_confirmation in Redis (did they reply "yes"?)
8. Enqueues task to Celery: {user_id, message, server_id, session_id}
9. Returns 200 to Telegram immediately
10. Celery worker picks up task, runs LangGraph graph
11. Worker calls send_telegram_message(chat_id, response)
12. WebSocket trace stream updated throughout
```

### WhatsApp message flow

Same as Telegram, with two differences:
- Form-encoded body parsed differently
- Twilio signature verified via `X-Twilio-Signature` header
- Response sent via Twilio Python client

### Message formatting

Telegram supports Markdown. WhatsApp supports plain text only.

```python
def format_response(response: str, platform: str) -> str:
    if platform == "telegram":
        return response  # LLM outputs markdown naturally
    elif platform == "whatsapp":
        # Strip markdown, keep structure readable
        return strip_markdown(response)
```

---

## 14. Request Lifecycle

Full trace of: **"Find all python files, zip them, tell me what each does"**

```
t=0ms    User sends Telegram message
t=5ms    FastAPI /webhook/telegram receives POST
t=8ms    Validates token, extracts user_id=abc, message
t=10ms   Checks rate limit → OK (pro tier)
t=12ms   Loads session from Redis → 3 previous messages
t=15ms   Enqueues Celery task, returns 200 to Telegram
t=20ms   Celery worker picks up task
t=25ms   Embeds user message via embedding-service
t=40ms   Qdrant query → 2 relevant memories retrieved:
         "workspace has many ML experiment scripts"
         "user prefers zipfiles over tarballs"
t=50ms   LangGraph graph starts, state initialized
t=55ms   Orchestrator (Haiku) → "multi_agent" (complex multi-step task)
t=200ms  Multi agent starts, system prompt includes server memories
t=350ms  Tool call: search_files("*.py") → docker exec
t=690ms  Tool result: 7 files found
t=700ms  Tool call: zip_files("/workspace", "backup.zip") → docker exec
t=920ms  Tool result: backup.zip created
t=930ms  Tool call: read_file("experiment1.py") → docker exec
...      [reads each file]
t=2100ms All files read
t=2500ms Sonnet generates summary of each file
t=2510ms Critic checks → SAFE (no destructive action)
t=2515ms Response streamed to WebSocket /ws/trace/sess_abc
t=2520ms Telegram message sent: summary + "backup.zip created in /workspace"
t=2525ms Command saved to MongoDB commands collection
t=2530ms New memory extracted: "user has 7 ML experiment scripts in /workspace"
t=2535ms Memory stored in Qdrant
t=2540ms Redis session updated with new messages
```

Total: **~2.5 seconds** for a complex 7-file multi-step task.

---

## 15. Security Model

### SSH key handling (BYOS)

```
User pastes private key in web UI (HTTPS only)
    → API receives key in request body (TLS in transit)
    → Immediately stored in HashiCorp Vault
    → Original key deleted from memory
    → Only vault_secret_path stored in MongoDB
    → Agent fetches key from Vault at connection time
    → Key lives in memory only during SSH session
    → Never written to disk, never logged
```

### Dangerous command protection

```
Every shell command passes through critic agent before execution
Critic runs on Sonnet (not Haiku) — no shortcuts on safety

BLOCKED outright (no confirmation possible):
    rm -rf /
    dd if=/dev/zero of=/dev/sda
    mkfs.*
    shutdown / poweroff / reboot (managed sandbox only)
    chmod 777 /etc/passwd

REQUIRES explicit "yes" confirmation:
    rm <any file>
    pkill / kill -9
    systemctl stop <service>
    apt remove / pip uninstall
    Any command with sudo

Confirmation expires in 60 seconds.
Second "yes" required for irreversible operations.
```

### API security

```
All /api/v1/* routes require valid Clerk JWT
JWT verified on every request (no session caching)
Rate limiting: 60 requests/minute per user_id (Redis token bucket)
Webhook endpoints validate platform signatures before processing
CORS restricted to ALLOWED_ORIGINS env var
```

---

## 16. Packaging and Deployment

### Local development

```bash
# 1. Clone and setup
git clone https://github.com/yourorg/GenOS
cd GenOS
cp .env.example .env
# fill in .env with your keys

# 2. Start all services
docker compose up --build

# 3. Expose for webhooks
ngrok http 8000

# 4. Register Telegram webhook
curl -X POST "https://api.telegram.org/bot{TOKEN}/setWebhook?url=https://{ngrok}/webhook/telegram"

# 5. Test without messaging
curl -X POST http://localhost:8000/api/v1/agent/run \
  -H "Authorization: Bearer {clerk_jwt}" \
  -H "Content-Type: application/json" \
  -d '{"message": "list /workspace", "server_id": "srv_abc"}'
```

### Production deployment (Railway for MVP)

```bash
# Install Railway CLI
npm install -g @railway/cli
railway login

# Deploy API
cd api
railway up

# Set env vars
railway variables set ANTHROPIC_API_KEY=sk-ant-...
railway variables set MONGO_URL=mongodb+srv://...
# (all vars from section 4)

# Deploy frontend
cd ../frontend
vercel --prod
```

### What to package in each image

**`GenOS-api` must include:**
- Python 3.11 + all pip dependencies
- Docker CLI (to exec into sandbox)
- OpenSSH client (for BYOS)
- Your application code
- `requirements.txt` pinned versions

**`GenOS-api` must NOT include:**
- Any `.env` files
- SSH private keys
- The sandbox tools (vim, htop, nmap etc.)
- ML models
- MongoDB / Redis binaries

**`GenOS-sandbox` must include:**
- Full Ubuntu 22.04 toolset (see section 5)
- Xvfb + scrot + xdotool
- Python 3.11 runtime
- Node.js runtime
- Common CLI tools users might need

**`GenOS-sandbox` must NOT include:**
- Your FastAPI application code
- LangGraph / Anthropic SDK
- Your `.env` or any secrets
- MongoDB / Redis

---

## 17. Scaling Playbook

### At 100 users

- Keep Railway + single FastAPI instance
- Add Celery workers (2–4) to handle concurrent agent runs
- Enable MongoDB Atlas auto-scaling
- Add Sentry + basic Axiom logging

### At 1,000 users

- Migrate to Fly.io (API) + Hetzner (compute)
- Add Prometheus + Grafana dashboards
- Implement tiered LLM routing (Haiku for simple, Sonnet for complex)
- Add Qdrant Cloud for vector memory
- Deploy HashiCorp Vault for SSH secret management
- Pre-warm sandbox container pool (10 containers ready per region)

### At 10,000 users

- Multi-region edge deployment on Fly.io
- k3s cluster for Celery worker auto-scaling
- Redis Cluster (3 nodes, replicated)
- MongoDB Atlas sharding by `user_id` hash
- WhatsApp Business API (replace Twilio sandbox)
- Dedicated agent marketplace infrastructure
- Separate billing service

### Cost at each scale

| Users | Monthly infra cost | MRR (at $19 ARPU, 30% paid) | Margin |
|-------|-------------------|------------------------------|--------|
| 100 | ~$80 | $570 | 86% |
| 1,000 | ~$400 | $5,700 | 93% |
| 10,000 | ~$2,500 | $57,000 | 96% |

---

*Document version 1.0 — GenOS Architecture*  
*Built for the hackathon, designed for scale.*
