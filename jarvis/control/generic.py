"""Best-effort cross-platform (macOS/Linux) controller.

This exists so the codebase runs and is testable on non-Windows machines
(e.g. for CI, or a macOS/Linux dev box). Primary production target is
Windows.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

from jarvis.control.base import Controller
from jarvis.observability import get_logger

log = get_logger(__name__)


class GenericController(Controller):
    def _run(self, cmd: list[str]) -> dict[str, Any]:
        try:
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)  # noqa: S603
            return {"ok": True, "command": " ".join(cmd)}
        except FileNotFoundError:
            return {"ok": False, "error": f"Not found: {cmd[0]}"}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": str(e)}

    def open_app(self, name: str) -> dict[str, Any]:
        if sys.platform == "darwin":
            return self._run(["open", "-a", name])
        # Linux: try direct binary, then xdg-open
        if shutil.which(name):
            return self._run([name])
        return self._run(["xdg-open", name])

    def open_website(self, url_or_query: str) -> dict[str, Any]:
        s = url_or_query.strip()
        if s.startswith(("http://", "https://")):
            url = s
        elif "." in s and " " not in s:
            url = f"https://{s}"
        else:
            url = f"https://www.google.com/search?q={quote_plus(s)}"
        try:
            webbrowser.open(url, new=2)
            return {"ok": True, "opened": url}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": str(e)}

    def set_volume(self, level: int) -> dict[str, Any]:
        level = max(0, min(100, int(level)))
        if sys.platform == "darwin":
            return self._run(["osascript", "-e", f"set volume output volume {level}"])
        # Linux via amixer (best effort)
        if shutil.which("amixer"):
            return self._run(["amixer", "-D", "pulse", "sset", "Master", f"{level}%"])
        return {"ok": False, "error": "No volume backend available on this OS."}

    def media_key(self, key: str) -> dict[str, Any]:
        return {"ok": False, "error": f"media_key not implemented on this OS: {key}"}

    def screenshot(self, save_path: str | None = None) -> dict[str, Any]:
        if save_path is None:
            Path("data/screenshots").mkdir(parents=True, exist_ok=True)
            save_path = f"data/screenshots/shot_{datetime.now():%Y%m%d_%H%M%S}.png"
        try:
            if sys.platform == "darwin":
                subprocess.run(["screencapture", "-x", save_path], check=True)  # noqa: S603
            elif shutil.which("scrot"):
                subprocess.run(["scrot", save_path], check=True)  # noqa: S603
            else:
                return {"ok": False, "error": "No screenshot backend"}
            return {"ok": True, "path": str(Path(save_path).resolve())}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": str(e)}

    def type_text(self, text: str) -> dict[str, Any]:
        return {"ok": False, "error": "type_text not implemented on this OS"}

    def press_keys(self, keys: str) -> dict[str, Any]:
        return {"ok": False, "error": "press_keys not implemented on this OS"}
