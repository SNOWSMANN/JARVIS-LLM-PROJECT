"""Shared audio helpers."""

from __future__ import annotations

from jarvis.config import settings
from jarvis.observability import get_logger

log = get_logger(__name__)


def input_device_index() -> int | None:
    v = settings.audio_input_device.strip()
    if not v:
        return None
    try:
        return int(v)
    except ValueError:
        # Match by device name substring
        try:
            import sounddevice as sd

            devs = sd.query_devices()
            for i, d in enumerate(devs):
                if v.lower() in d["name"].lower() and d["max_input_channels"] > 0:
                    return i
        except Exception as e:  # noqa: BLE001
            log.warning("Could not match audio input device: {}", e)
    return None


def output_device_index() -> int | None:
    v = settings.audio_output_device.strip()
    if not v:
        return None
    try:
        return int(v)
    except ValueError:
        try:
            import sounddevice as sd

            devs = sd.query_devices()
            for i, d in enumerate(devs):
                if v.lower() in d["name"].lower() and d["max_output_channels"] > 0:
                    return i
        except Exception as e:  # noqa: BLE001
            log.warning("Could not match audio output device: {}", e)
    return None
