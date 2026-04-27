"""Tool registry for the Jarvis agent.

A Tool is:
- A Python callable
- An OpenAI-compatible JSON schema describing its name, args, and description
- Optional `requires_confirmation` flag for destructive actions

The registry produces the `tools=[...]` array we pass to the LLM, and
dispatches tool calls by name.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from jarvis.observability import get_logger

log = get_logger(__name__)


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]
    func: Callable[..., Any]
    requires_confirmation: bool = False
    category: str = "general"

    def to_openai(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


@dataclass
class ToolRegistry:
    _tools: dict[str, Tool] = field(default_factory=dict)

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            log.warning("Tool '{}' re-registered", tool.name)
        self._tools[tool.name] = tool
        log.debug("Registered tool: {} ({})", tool.name, tool.category)

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def all(self) -> list[Tool]:
        return list(self._tools.values())

    def schemas(self) -> list[dict[str, Any]]:
        return [t.to_openai() for t in self._tools.values()]

    def call(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        tool = self.get(name)
        if tool is None:
            return {"ok": False, "error": f"Unknown tool: {name}"}
        try:
            result = tool.func(**(arguments or {}))
            if isinstance(result, dict) and "ok" in result:
                return result
            return {"ok": True, "result": result}
        except TypeError as e:
            return {"ok": False, "error": f"Bad arguments for {name}: {e}"}
        except Exception as e:  # noqa: BLE001
            log.exception("Tool {} failed", name)
            return {"ok": False, "error": str(e)}


default_registry = ToolRegistry()
