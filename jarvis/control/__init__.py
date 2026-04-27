"""OS-specific computer-control adapter.

Loads the correct backend at import time:
- Windows → jarvis.control.windows
- macOS / Linux → jarvis.control.generic (best-effort)
"""

from __future__ import annotations

import platform

from jarvis.observability import get_logger

log = get_logger(__name__)

_system = platform.system()

if _system == "Windows":
    from jarvis.control.windows import WindowsController as _Controller
elif _system in {"Darwin", "Linux"}:
    from jarvis.control.generic import GenericController as _Controller
else:
    from jarvis.control.generic import GenericController as _Controller

controller = _Controller()
log.info("Control backend: {} ({})", type(controller).__name__, _system)

__all__ = ["controller"]
