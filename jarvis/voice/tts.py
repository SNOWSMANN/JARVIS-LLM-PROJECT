"""Text-to-speech: ElevenLabs primary, pyttsx3 fallback.

Streams audio directly to the default output device. Keeps a lightweight
on-disk cache so repeated phrases (e.g. "At your service, Sir.") don't
burn API credits.
"""

from __future__ import annotations

import hashlib
import threading
from pathlib import Path

from jarvis.config import settings
from jarvis.observability import get_logger

log = get_logger(__name__)

_CACHE_DIR = Path("data/audio_cache")


class Speaker:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        self._backend = "elevenlabs" if settings.has_elevenlabs else settings.tts_fallback
        log.info("TTS backend: {}", self._backend)

    def say(self, text: str) -> None:
        """Speak text synchronously."""
        if not text.strip():
            return
        with self._lock:
            if self._backend == "elevenlabs":
                try:
                    self._say_elevenlabs(text)
                    return
                except Exception as e:  # noqa: BLE001
                    log.warning("ElevenLabs TTS failed, falling back: {}", e)
            self._say_pyttsx3(text)

    # ---------- ElevenLabs ----------

    def _say_elevenlabs(self, text: str) -> None:
        cache_key = hashlib.sha1(
            (settings.elevenlabs_voice_id + "|" + settings.elevenlabs_model + "|" + text).encode()
        ).hexdigest()
        cache_path = _CACHE_DIR / f"{cache_key}.mp3"
        if not cache_path.exists():
            import requests

            url = (
                "https://api.elevenlabs.io/v1/text-to-speech/"
                + settings.elevenlabs_voice_id
                + "?output_format=mp3_44100_128"
            )
            headers = {
                "xi-api-key": settings.elevenlabs_api_key,
                "Content-Type": "application/json",
                "Accept": "audio/mpeg",
            }
            payload = {
                "text": text,
                "model_id": settings.elevenlabs_model,
                "voice_settings": {"stability": 0.4, "similarity_boost": 0.8},
            }
            r = requests.post(url, headers=headers, json=payload, timeout=30)
            r.raise_for_status()
            cache_path.write_bytes(r.content)
        self._play_mp3(cache_path)

    def _play_mp3(self, path: Path) -> None:
        """Play an MP3 via pydub → numpy → sounddevice."""
        from pydub import AudioSegment

        seg = AudioSegment.from_file(path, format="mp3")
        seg = seg.set_channels(1).set_frame_rate(44100)
        import numpy as np
        import sounddevice as sd

        from jarvis.voice.audio import output_device_index

        samples = np.array(seg.get_array_of_samples(), dtype=np.int16)
        sd.play(samples, seg.frame_rate, device=output_device_index())
        sd.wait()

    # ---------- pyttsx3 fallback ----------

    def _say_pyttsx3(self, text: str) -> None:
        try:
            import pyttsx3

            engine = pyttsx3.init()
            engine.setProperty("rate", 185)
            # Prefer a male voice if available.
            for v in engine.getProperty("voices"):
                if "male" in (v.name or "").lower() or "david" in (v.id or "").lower():
                    engine.setProperty("voice", v.id)
                    break
            engine.say(text)
            engine.runAndWait()
        except Exception as e:  # noqa: BLE001
            log.error("pyttsx3 failed: {}", e)
            # Last-resort console fallback
            print(f"[Jarvis] {text}")
