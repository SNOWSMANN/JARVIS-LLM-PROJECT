"""Shared data types used across Jarvis modules."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Role(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class ConversationTurn(BaseModel):
    role: Role
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    tool_calls: list[ToolCall] | None = None
    tool_call_id: str | None = None


class ToolCall(BaseModel):
    id: str
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class ToolResult(BaseModel):
    call_id: str
    name: str
    ok: bool
    content: str
    error: str | None = None


class AgentResponse(BaseModel):
    text: str
    tool_calls: list[ToolCall] = Field(default_factory=list)
    tool_results: list[ToolResult] = Field(default_factory=list)
    confidence: float = 1.0
    needs_clarification: bool = False
    reasoning: str | None = None


class Intent(str, Enum):
    """High-level classification of what the user wants."""

    CHAT = "chat"
    QUESTION = "question"
    OPEN_APP = "open_app"
    OPEN_WEBSITE = "open_website"
    WEB_SEARCH = "web_search"
    FILE_OP = "file_op"
    SYSTEM_CONTROL = "system_control"
    MEMORY_RECALL = "memory_recall"
    MEMORY_STORE = "memory_store"
    SHUTDOWN = "shutdown"
    UNKNOWN = "unknown"


ConversationTurn.model_rebuild()
