"""Agent orchestrator — the Jarvis "brain" loop.

Flow per user turn:
  1. Short-term memory: last N turns
  2. Long-term memory recall: vector search on the user's input
  3. Build messages = [system, recalled memories as system note, history..., user]
  4. Ask LLM with tool schemas
  5. If the LLM asked for tools → execute → feed results back → ask again
  6. Return final text + tool trace

Safety:
- Tools marked `requires_confirmation=True` are NOT auto-executed unless
  the user's message contains explicit consent phrasing, OR we're running
  non-interactively (`trust_level="high"`). Otherwise the agent narrates
  the intended action and asks for confirmation.
"""

from __future__ import annotations

from typing import Any

from jarvis.agent.llm import LLMClient
from jarvis.agent.personality import get_system_prompt
from jarvis.config import settings
from jarvis.core.types import AgentResponse, ToolCall, ToolResult
from jarvis.memory import MemoryStore
from jarvis.observability import get_logger
from jarvis.tools import default_registry

log = get_logger(__name__)

_CONFIRM_PHRASES = (
    "yes",
    "yep",
    "go ahead",
    "do it",
    "confirm",
    "please",
    "sure",
    "ok",
    "okay",
    "approved",
)


class Agent:
    def __init__(
        self,
        memory: MemoryStore,
        llm: LLMClient | None = None,
        conversation_id: int | None = None,
    ) -> None:
        self.memory = memory
        self.llm = llm or LLMClient()
        self.conversation_id = conversation_id or memory.start_conversation()
        self._system = get_system_prompt()

    # ---------- public API ----------

    def handle(self, user_text: str, trust_level: str = "normal") -> AgentResponse:
        """Process one user turn end-to-end."""
        user_text = user_text.strip()
        if not user_text:
            return AgentResponse(text="", confidence=0.0)

        self.memory.add_turn(self.conversation_id, "user", user_text)

        if not self.llm.available():
            fallback = (
                f"I'm listening, {settings.jarvis_user_name}, but I have no language "
                "model configured. Please add an OpenAI key to the environment."
            )
            self.memory.add_turn(self.conversation_id, "assistant", fallback)
            return AgentResponse(text=fallback, confidence=0.3)

        messages = self._build_messages(user_text)
        tools = default_registry.schemas()

        tool_calls_made: list[ToolCall] = []
        tool_results_collected: list[ToolResult] = []

        # Multi-step tool loop, with a cap to prevent runaway.
        for step in range(5):
            resp = self.llm.chat(messages=messages, tools=tools)
            content = resp.get("content") or ""
            tool_calls = resp.get("tool_calls") or []

            if not tool_calls:
                if content:
                    self.memory.add_turn(self.conversation_id, "assistant", content)
                self.memory.audit(
                    action="agent.respond",
                    target=content[:80],
                    ok=True,
                    detail={"steps": step + 1},
                )
                return AgentResponse(
                    text=content,
                    tool_calls=tool_calls_made,
                    tool_results=tool_results_collected,
                )

            # Append the model's own tool-call message to conversation for the
            # next round (OpenAI expects tool outputs to follow tool_calls).
            messages.append(
                {
                    "role": "assistant",
                    "content": content or None,
                    "tool_calls": [
                        {
                            "id": tc["id"],
                            "type": "function",
                            "function": {
                                "name": tc["name"],
                                "arguments": _json_dump(tc["arguments"]),
                            },
                        }
                        for tc in tool_calls
                    ],
                }
            )

            for tc in tool_calls:
                result = self._execute_tool(tc, user_text, trust_level)
                tool_calls_made.append(
                    ToolCall(id=tc["id"], name=tc["name"], arguments=tc["arguments"])
                )
                tool_results_collected.append(result)

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "name": tc["name"],
                        "content": _json_dump(
                            {"ok": result.ok, "content": result.content, "error": result.error}
                        ),
                    }
                )

        # Safety bail-out
        bail = "I seem to be stuck in a loop. Let me try again — what would you like me to do?"
        self.memory.add_turn(self.conversation_id, "assistant", bail)
        return AgentResponse(
            text=bail,
            tool_calls=tool_calls_made,
            tool_results=tool_results_collected,
            confidence=0.2,
        )

    # ---------- internals ----------

    def _build_messages(self, user_text: str) -> list[dict[str, Any]]:
        msgs: list[dict[str, Any]] = [{"role": "system", "content": self._system}]

        # Long-term recall
        hits = self.memory.recall(user_text, n=4)
        if hits:
            recalled = "\n".join(f"- {h['text']}" for h in hits if h.get("text"))
            if recalled.strip():
                msgs.append(
                    {
                        "role": "system",
                        "content": (
                            "Potentially relevant things you remember about the user "
                            "or past context (use silently; cite naturally only if "
                            "useful):\n" + recalled
                        ),
                    }
                )

        # Short-term history
        turns = self.memory.recent_turns(
            self.conversation_id, n=settings.memory_short_term_window
        )
        for t in turns:
            if t.role in {"user", "assistant"}:
                msgs.append({"role": t.role, "content": t.content})

        # Current user turn (already persisted, but we still want it as the last msg)
        if not msgs or msgs[-1].get("content") != user_text:
            msgs.append({"role": "user", "content": user_text})
        return msgs

    def _execute_tool(
        self, tc: dict[str, Any], user_text: str, trust_level: str
    ) -> ToolResult:
        tool = default_registry.get(tc["name"])
        if tool is None:
            return ToolResult(
                call_id=tc["id"],
                name=tc["name"],
                ok=False,
                content="",
                error=f"Unknown tool: {tc['name']}",
            )

        if (
            tool.requires_confirmation
            and trust_level != "high"
            and not _user_consented(user_text)
        ):
            msg = f"Tool '{tool.name}' requires explicit confirmation from the user."
            self.memory.audit(
                action="tool.skip",
                target=tool.name,
                ok=False,
                detail={"reason": "needs_confirmation"},
            )
            return ToolResult(
                call_id=tc["id"], name=tool.name, ok=False, content="", error=msg
            )

        result = default_registry.call(tool.name, tc["arguments"])
        self.memory.audit(
            action="tool.call",
            target=tool.name,
            ok=bool(result.get("ok", False)),
            detail={"args": tc["arguments"], "result": _truncate(result)},
        )
        return ToolResult(
            call_id=tc["id"],
            name=tool.name,
            ok=bool(result.get("ok", False)),
            content=_json_dump(result)[:4000],
            error=None if result.get("ok", False) else str(result.get("error", "")),
        )


def _user_consented(text: str) -> bool:
    t = text.lower().strip()
    return any(p in t for p in _CONFIRM_PHRASES)


def _json_dump(obj: Any) -> str:
    import json

    try:
        return json.dumps(obj, default=str)
    except Exception:  # noqa: BLE001
        return str(obj)


def _truncate(obj: Any, limit: int = 500) -> Any:
    s = _json_dump(obj)
    return s if len(s) <= limit else s[:limit] + "…"
