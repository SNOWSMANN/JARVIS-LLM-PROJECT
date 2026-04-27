"""Wake word detection using openWakeWord.

Runs continuously on the mic, yields when the wake word ("hey jarvis") is
detected with confidence above threshold.
"""

from __future__ import annotations

import queue
import threading
from collections.abc import Iterator

import numpy as np

from jarvis.config import settings
from jarvis.observability import get_logger
from jarvis.voice.audio import input_device_index

log = get_logger(__name__)

_CHUNK_MS = 80  # openwakeword works well with 80ms chunks
_SAMPLE_RATE = 16000
_CHUNK_SAMPLES = int(_SAMPLE_RATE * _CHUNK_MS / 1000)


class WakeWordListener:
    def __init__(self) -> None:
        self._stop = threading.Event()
        self._audio_q: queue.Queue[np.ndarray] = queue.Queue()
        self._model = None

    def _load_model(self) -> None:
        if self._model is not None:
            return
        try:
            from openwakeword.model import Model

            # First call downloads the model. Use the 'hey_jarvis' community model.
            self._model = Model(
                wakeword_models=[settings.wake_word_model],
                inference_framework="onnx",
            )
            log.info("Wake word model loaded: {}", settings.wake_word_model)
        except Exception as e:  # noqa: BLE001
            log.error("Wake word model load failed: {}", e)
            raise

    def listen(self) -> Iterator[str]:
        """Blocking generator that yields the wake-word model name on each detection."""
        self._load_model()
        import sounddevice as sd

        def _callback(indata, frames, time_info, status):  # noqa: ANN001
            if status:
                log.debug("Wake mic status: {}", status)
            # indata is float32 [-1, 1]; openwakeword wants int16
            mono = indata[:, 0] if indata.ndim > 1 else indata
            pcm = (np.clip(mono, -1.0, 1.0) * 32767).astype(np.int16)
            self._audio_q.put(pcm.copy())

        dev = input_device_index()
        with sd.InputStream(
            samplerate=_SAMPLE_RATE,
            channels=1,
            dtype="float32",
            blocksize=_CHUNK_SAMPLES,
            device=dev,
            callback=_callback,
        ):
            log.info(
                "Listening for wake word '{}' (threshold={})",
                settings.wake_word_model,
                settings.wake_word_threshold,
            )
            while not self._stop.is_set():
                try:
                    chunk = self._audio_q.get(timeout=0.25)
                except queue.Empty:
                    continue
                try:
                    preds = self._model.predict(chunk)  # type: ignore[union-attr]
                except Exception as e:  # noqa: BLE001
                    log.warning("Wake predict error: {}", e)
                    continue
                for name, score in preds.items():
                    if score >= settings.wake_word_threshold:
                        log.info("Wake word detected: {} ({:.2f})", name, score)
                        # Drain queue briefly so the STT stage starts fresh.
                        with self._audio_q.mutex:
                            self._audio_q.queue.clear()
                        yield name

    def stop(self) -> None:
        self._stop.set()
