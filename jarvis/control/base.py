"""Abstract controller interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class Controller(ABC):
    @abstractmethod
    def open_app(self, name: str) -> dict[str, Any]: ...

    @abstractmethod
    def open_website(self, url_or_query: str) -> dict[str, Any]: ...

    @abstractmethod
    def set_volume(self, level: int) -> dict[str, Any]: ...

    @abstractmethod
    def media_key(self, key: str) -> dict[str, Any]: ...

    @abstractmethod
    def screenshot(self, save_path: str | None = None) -> dict[str, Any]: ...

    @abstractmethod
    def type_text(self, text: str) -> dict[str, Any]: ...

    @abstractmethod
    def press_keys(self, keys: str) -> dict[str, Any]: ...
