"""FastAPI server exposing the Jarvis brain over HTTP.

Phase 2 mobile clients (iOS / Android / web) can connect to this endpoint
and get the same reasoning + memory + tool execution as the local voice
assistant.

Security: a static API key (`SERVER_API_KEY`) is required in the
`Authorization: Bearer …` header. Bind to 127.0.0.1 by default; change
`SERVER_HOST` only if you know what you're doing and are behind a VPN.
"""

from __future__ import annotations

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel

from jarvis.agent import Agent
from jarvis.config import settings
from jarvis.memory import MemoryStore
from jarvis.observability import get_logger

log = get_logger(__name__)


class ChatRequest(BaseModel):
    message: str
    trust_level: str = "normal"


class ChatResponse(BaseModel):
    text: str
    tool_calls: list[dict] = []
    tool_results: list[dict] = []


def _require_auth(authorization: str | None = Header(default=None)) -> None:
    expected = f"Bearer {settings.server_api_key}"
    if settings.server_api_key == "change-me":
        log.warning("SERVER_API_KEY is default — set a strong key in .env before remote use.")
    if authorization != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")


def build_app(memory: MemoryStore | None = None) -> FastAPI:
    app = FastAPI(title="Jarvis", version="0.1.0")

    mem = memory or MemoryStore()
    mem.start()
    agent = Agent(memory=mem)

    @app.get("/healthz")
    def health() -> dict:
        return {"ok": True, "name": settings.jarvis_name}

    @app.post("/chat", response_model=ChatResponse)
    def chat(req: ChatRequest, _auth: None = Depends(_require_auth)) -> ChatResponse:
        resp = agent.handle(req.message, trust_level=req.trust_level)
        return ChatResponse(
            text=resp.text,
            tool_calls=[tc.model_dump() for tc in resp.tool_calls],
            tool_results=[tr.model_dump() for tr in resp.tool_results],
        )

    return app
