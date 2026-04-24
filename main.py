from contextlib import asynccontextmanager
from fastapi import FastAPI
import uvicorn
from api.agents import router as agents_router
from connectors.redis_connector import RedisClient


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──────────────────────────────────────────────────
    RedisClient.connect()
    yield
    # ── Shutdown ─────────────────────────────────────────────────
    await RedisClient.disconnect()


app = FastAPI(
    title="GenOS Agent API",
    description="Simple API to execute commands on remote servers using AI agents.",
    lifespan=lifespan
)

app.include_router(agents_router, prefix="/api", tags=["Agents"])


@app.get("/")
def health_check():
    return {"status": "ok", "message": "GenOS API is running"}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)