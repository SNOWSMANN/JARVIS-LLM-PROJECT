"""LLM client with OpenAI primary + Ollama fallback + retry."""

from __future__ import annotations

from typing import Any

from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from jarvis.config import settings
from jarvis.observability import get_logger

log = get_logger(__name__)


class LLMError(Exception):
    pass


class LLMClient:
    """Thin wrapper over OpenAI's chat/completions with tool calling.

    Falls back to Ollama's OpenAI-compatible endpoint if OpenAI fails and
    OLLAMA_ENABLED is true.
    """

    def __init__(self) -> None:
        self._openai = None
        self._ollama = None
        if settings.has_openai:
            try:
                from openai import OpenAI

                self._openai = OpenAI(api_key=settings.openai_api_key)
                log.info("OpenAI client ready (model={})", settings.openai_model)
            except Exception as e:  # noqa: BLE001
                log.warning("OpenAI init failed: {}", e)

        if settings.ollama_enabled:
            try:
                from openai import OpenAI

                self._ollama = OpenAI(
                    api_key="ollama",
                    base_url=settings.ollama_base_url.rstrip("/") + "/v1",
                )
                log.info("Ollama fallback ready ({})", settings.ollama_model)
            except Exception as e:  # noqa: BLE001
                log.warning("Ollama fallback init failed: {}", e)

        if self._openai is None and self._ollama is None:
            log.warning(
                "No LLM backend configured. Set OPENAI_API_KEY or enable Ollama."
            )

    def available(self) -> bool:
        return self._openai is not None or self._ollama is not None

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    def _openai_chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        model: str,
    ) -> Any:
        assert self._openai is not None
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": 0.4,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        return self._openai.chat.completions.create(**kwargs)

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
    ) -> dict[str, Any]:
        """Run a chat completion. Returns a dict:
        {
            "content": str | None,
            "tool_calls": [{id, name, arguments(dict)}, ...],
            "raw": original message dict,
        }
        """
        last_err: Exception | None = None
        model = model or settings.openai_model

        if self._openai is not None:
            try:
                resp = self._openai_chat(messages, tools, model)
                return self._normalize(resp)
            except Exception as e:  # noqa: BLE001
                log.warning("OpenAI chat failed: {}", e)
                last_err = e

        if self._ollama is not None:
            try:
                resp = self._ollama.chat.completions.create(
                    model=settings.ollama_model,
                    messages=messages,
                    tools=tools,
                    temperature=0.4,
                )
                return self._normalize(resp)
            except Exception as e:  # noqa: BLE001
                log.error("Ollama chat failed: {}", e)
                last_err = e

        raise LLMError(f"No LLM backend available. Last error: {last_err}")

    @staticmethod
    def _normalize(resp: Any) -> dict[str, Any]:
        import json

        choice = resp.choices[0]
        msg = choice.message
        content = msg.content or ""
        tool_calls = []
        for tc in getattr(msg, "tool_calls", None) or []:
            try:
                args = json.loads(tc.function.arguments) if tc.function.arguments else {}
            except json.JSONDecodeError:
                args = {"_raw": tc.function.arguments}
            tool_calls.append(
                {"id": tc.id, "name": tc.function.name, "arguments": args}
            )
        return {"content": content, "tool_calls": tool_calls, "raw": msg}
