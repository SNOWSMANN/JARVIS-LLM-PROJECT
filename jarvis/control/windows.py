"""Windows-specific computer control.

All functions return {"ok": bool, ...} dicts so they're safe to bubble up
through the tool layer directly into LLM responses.
"""

from __future__ import annotations

import os
import re
import subprocess
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

from jarvis.control.base import Controller
from jarvis.observability import get_logger

log = get_logger(__name__)


# Common apps — friendly name → Windows executable / URI / store ID.
# We try these in order: exact match → "start shell:..." → "where <name>".
_APP_ALIASES: dict[str, list[str]] = {
    "chrome": ["chrome.exe", "chrome"],
    "google chrome": ["chrome.exe", "chrome"],
    "edge": ["msedge.exe", "microsoft-edge:"],
    "microsoft edge": ["msedge.exe", "microsoft-edge:"],
    "firefox": ["firefox.exe"],
    "notepad": ["notepad.exe"],
    "calculator": ["calc.exe"],
    "calc": ["calc.exe"],
    "explorer": ["explorer.exe"],
    "file explorer": ["explorer.exe"],
    "files": ["explorer.exe"],
    "settings": ["ms-settings:"],
    "task manager": ["taskmgr.exe"],
    "cmd": ["cmd.exe"],
    "command prompt": ["cmd.exe"],
    "powershell": ["powershell.exe"],
    "terminal": ["wt.exe", "powershell.exe"],
    "vscode": ["code.cmd", "code"],
    "visual studio code": ["code.cmd", "code"],
    "code": ["code.cmd", "code"],
    "spotify": ["spotify.exe"],
    "discord": ["discord.exe"],
    "whatsapp": ["whatsapp:"],
    "paint": ["mspaint.exe"],
    "word": ["winword.exe"],
    "excel": ["excel.exe"],
    "powerpoint": ["powerpnt.exe"],
    "outlook": ["outlook.exe"],
    "camera": ["microsoft.windows.camera:"],
}


def _looks_like_url(s: str) -> bool:
    return bool(re.match(r"^(https?://|www\.|[a-z0-9.-]+\.[a-z]{2,}(/|$))", s.strip(), re.I))


class WindowsController(Controller):
    # ---------- apps / URLs ----------

    def open_app(self, name: str) -> dict[str, Any]:
        key = name.strip().lower()
        candidates = _APP_ALIASES.get(key, [name])

        for candidate in candidates:
            try:
                if candidate.endswith(":") or "://" in candidate:
                    # URI scheme like ms-settings: → use os.startfile
                    os.startfile(candidate)  # noqa: SIM115  type: ignore[attr-defined]
                    log.info("Opened URI '{}' for app '{}'", candidate, name)
                    return {"ok": True, "opened": candidate}
                subprocess.Popen(  # noqa: S603
                    ["cmd", "/c", "start", "", candidate], shell=False
                )
                log.info("Launched '{}' for app '{}'", candidate, name)
                return {"ok": True, "opened": candidate}
            except Exception as e:  # noqa: BLE001
                log.debug("Candidate '{}' failed: {}", candidate, e)
                continue

        # Last resort: let Windows resolve it via the Run dialog.
        try:
            subprocess.Popen(["cmd", "/c", "start", "", name], shell=False)  # noqa: S603
            return {"ok": True, "opened": name, "resolution": "shell"}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": f"Could not open '{name}': {e}"}

    def open_website(self, url_or_query: str) -> dict[str, Any]:
        s = url_or_query.strip()
        if _looks_like_url(s):
            url = s if s.startswith(("http://", "https://")) else f"https://{s}"
        else:
            url = f"https://www.google.com/search?q={quote_plus(s)}"
        try:
            webbrowser.open(url, new=2)
            return {"ok": True, "opened": url}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": str(e)}

    # ---------- audio ----------

    def set_volume(self, level: int) -> dict[str, Any]:
        level = max(0, min(100, int(level)))
        try:
            from comtypes import CLSCTX_ALL  # type: ignore[import-not-found]
            from pycaw.pycaw import (  # type: ignore[import-not-found]
                AudioUtilities,
                IAudioEndpointVolume,
            )

            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = interface.QueryInterface(IAudioEndpointVolume)
            volume.SetMasterVolumeLevelScalar(level / 100.0, None)
            return {"ok": True, "level": level}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": f"pycaw unavailable: {e}"}

    def media_key(self, key: str) -> dict[str, Any]:
        mapping = {
            "play_pause": "playpause",
            "next": "nexttrack",
            "prev": "prevtrack",
            "mute": "volumemute",
            "vol_up": "volumeup",
            "vol_down": "volumedown",
        }
        pyauto_key = mapping.get(key, key)
        try:
            import pyautogui  # type: ignore[import-not-found]

            pyautogui.press(pyauto_key)
            return {"ok": True, "key": pyauto_key}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": str(e)}

    # ---------- screen / input ----------

    def screenshot(self, save_path: str | None = None) -> dict[str, Any]:
        try:
            import pyautogui  # type: ignore[import-not-found]

            if save_path is None:
                Path("data/screenshots").mkdir(parents=True, exist_ok=True)
                save_path = f"data/screenshots/shot_{datetime.now():%Y%m%d_%H%M%S}.png"
            img = pyautogui.screenshot()
            img.save(save_path)
            return {"ok": True, "path": str(Path(save_path).resolve())}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": str(e)}

    def type_text(self, text: str) -> dict[str, Any]:
        try:
            import pyautogui  # type: ignore[import-not-found]

            pyautogui.typewrite(text, interval=0.02)
            return {"ok": True, "typed_chars": len(text)}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": str(e)}

    def press_keys(self, keys: str) -> dict[str, Any]:
        try:
            import pyautogui  # type: ignore[import-not-found]

            parts = [k.strip().lower() for k in keys.split("+") if k.strip()]
            if len(parts) == 1:
                pyautogui.press(parts[0])
            else:
                pyautogui.hotkey(*parts)
            return {"ok": True, "keys": keys}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": str(e)}
