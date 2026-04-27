"""Built-in tools available to the Jarvis agent.

These tools are registered into `default_registry` by `register_builtin_tools()`.

Tools intentionally depend only on the `control` layer for OS-specific work,
so swapping Windows ↔ macOS ↔ Linux is a matter of providing a different
control adapter.
"""

from __future__ import annotations

from typing import Any

from jarvis.control import controller
from jarvis.memory import MemoryStore
from jarvis.observability import get_logger
from jarvis.tools.registry import Tool, default_registry

log = get_logger(__name__)


# ---------- web / system-info tools ----------


def _web_search(query: str, max_results: int = 5) -> dict[str, Any]:
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        return {"ok": False, "error": "duckduckgo-search not installed"}

    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"Search failed: {e}"}

    brief = [
        {"title": r.get("title"), "url": r.get("href"), "snippet": r.get("body")}
        for r in results
    ]
    return {"ok": True, "query": query, "results": brief}


def _get_time() -> dict[str, Any]:
    from datetime import datetime

    now = datetime.now()
    return {
        "ok": True,
        "iso": now.isoformat(),
        "human": now.strftime("%A, %d %B %Y, %H:%M"),
    }


def _system_info() -> dict[str, Any]:
    import platform

    import psutil

    vm = psutil.virtual_memory()
    return {
        "ok": True,
        "platform": platform.platform(),
        "python": platform.python_version(),
        "cpu_percent": psutil.cpu_percent(interval=0.1),
        "memory_percent": vm.percent,
        "memory_available_mb": vm.available // (1024 * 1024),
        "battery": _battery(),
    }


def _battery() -> dict[str, Any] | None:
    try:
        import psutil

        b = psutil.sensors_battery()
        if b is None:
            return None
        return {"percent": b.percent, "plugged": b.power_plugged}
    except Exception:  # noqa: BLE001
        return None


# ---------- computer-control tools ----------


def _open_app(name: str) -> dict[str, Any]:
    return controller.open_app(name)


def _open_website(url_or_query: str) -> dict[str, Any]:
    return controller.open_website(url_or_query)


def _set_volume(level: int) -> dict[str, Any]:
    return controller.set_volume(level)


def _media_play_pause() -> dict[str, Any]:
    return controller.media_key("play_pause")


def _media_next() -> dict[str, Any]:
    return controller.media_key("next")


def _media_previous() -> dict[str, Any]:
    return controller.media_key("prev")


def _screenshot(save_path: str | None = None) -> dict[str, Any]:
    return controller.screenshot(save_path=save_path)


def _type_text(text: str) -> dict[str, Any]:
    return controller.type_text(text)


def _press_keys(keys: str) -> dict[str, Any]:
    return controller.press_keys(keys)


# ---------- memory tools ----------


def build_memory_tools(memory: MemoryStore) -> list[Tool]:
    def _remember(
        content: str,
        kind: str = "fact",
        importance: float = 0.6,
    ) -> dict[str, Any]:
        mid = memory.remember(content=content, kind=kind, importance=importance)
        return {"ok": mid >= 0, "memory_id": mid}

    def _recall(query: str, n: int = 5) -> dict[str, Any]:
        hits = memory.recall(query, n=n)
        return {"ok": True, "results": hits}

    return [
        Tool(
            name="remember",
            description=(
                "Store a durable long-term memory about the user, their preferences, "
                "relationships, events, commitments, or emotional context. Use this "
                "whenever the user shares something worth recalling later."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "The fact to remember, written concisely in third person.",
                    },
                    "kind": {
                        "type": "string",
                        "enum": [
                            "fact",
                            "preference",
                            "event",
                            "habit",
                            "relationship",
                            "trust",
                            "emotional",
                        ],
                        "default": "fact",
                    },
                    "importance": {
                        "type": "number",
                        "minimum": 0,
                        "maximum": 1,
                        "default": 0.6,
                        "description": "0.0–1.0. Higher = more likely to be retained.",
                    },
                },
                "required": ["content"],
            },
            func=_remember,
            category="memory",
        ),
        Tool(
            name="recall",
            description=(
                "Semantically search long-term memory for relevant facts, past "
                "conversations, or preferences related to the query."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "n": {"type": "integer", "default": 5, "minimum": 1, "maximum": 20},
                },
                "required": ["query"],
            },
            func=_recall,
            category="memory",
        ),
    ]


# ---------- registration ----------


def register_builtin_tools(memory: MemoryStore) -> None:
    """Register all built-in tools into the default registry."""

    tools: list[Tool] = [
        Tool(
            name="open_app",
            description=(
                "Open a desktop application by name (e.g. 'chrome', 'notepad', "
                "'vscode', 'spotify', 'calculator'). Case-insensitive."
            ),
            parameters={
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
            },
            func=_open_app,
            category="control",
        ),
        Tool(
            name="open_website",
            description=(
                "Open a URL in the default browser, or search the web for a query "
                "if the input isn't a URL."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "url_or_query": {
                        "type": "string",
                        "description": "Full URL (https://…) or a search query.",
                    }
                },
                "required": ["url_or_query"],
            },
            func=_open_website,
            category="control",
        ),
        Tool(
            name="web_search",
            description="Search the public web and return the top results.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "max_results": {"type": "integer", "default": 5, "minimum": 1, "maximum": 10},
                },
                "required": ["query"],
            },
            func=_web_search,
            category="knowledge",
        ),
        Tool(
            name="get_time",
            description="Return the current local date and time.",
            parameters={"type": "object", "properties": {}},
            func=_get_time,
            category="system",
        ),
        Tool(
            name="system_info",
            description="Return CPU, memory, and battery status for the host machine.",
            parameters={"type": "object", "properties": {}},
            func=_system_info,
            category="system",
        ),
        Tool(
            name="set_volume",
            description="Set the system master volume to a percentage (0–100).",
            parameters={
                "type": "object",
                "properties": {
                    "level": {"type": "integer", "minimum": 0, "maximum": 100}
                },
                "required": ["level"],
            },
            func=_set_volume,
            category="control",
        ),
        Tool(
            name="media_play_pause",
            description="Toggle play/pause of the currently active media.",
            parameters={"type": "object", "properties": {}},
            func=_media_play_pause,
            category="control",
        ),
        Tool(
            name="media_next",
            description="Skip to the next media track.",
            parameters={"type": "object", "properties": {}},
            func=_media_next,
            category="control",
        ),
        Tool(
            name="media_previous",
            description="Go to the previous media track.",
            parameters={"type": "object", "properties": {}},
            func=_media_previous,
            category="control",
        ),
        Tool(
            name="screenshot",
            description="Capture a screenshot of the primary display. Returns the saved file path.",
            parameters={
                "type": "object",
                "properties": {
                    "save_path": {"type": "string"},
                },
            },
            func=_screenshot,
            category="vision",
        ),
        Tool(
            name="type_text",
            description=(
                "Type the given text at the current keyboard focus. Use carefully; "
                "prefer `open_app` + explicit user instruction for inputs."
            ),
            parameters={
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
            func=_type_text,
            requires_confirmation=True,
            category="control",
        ),
        Tool(
            name="press_keys",
            description=(
                "Press a keyboard combo. Use pyautogui syntax, e.g. 'ctrl+c', "
                "'alt+tab', 'win+d', 'enter'."
            ),
            parameters={
                "type": "object",
                "properties": {"keys": {"type": "string"}},
                "required": ["keys"],
            },
            func=_press_keys,
            category="control",
        ),
    ]

    for t in tools:
        default_registry.register(t)

    for t in build_memory_tools(memory):
        default_registry.register(t)

    log.info("Registered {} built-in tools", len(default_registry.all()))
