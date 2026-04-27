"""Speech-to-text with voice-activity detection.

After wake word fires, we:
1. Start recording from the mic at 16 kHz.
2. Use WebRTC VAD to find the end of the user's utterance (silence for N ms).
3. Transcribe the buffered audio with faster-whisper.

Cap the utterance length (max 20s by default) to protect against bad VAD.
"""

from __future__ import annotations

import collections
import time

import numpy as np

from jarvis.config import settings
from jarvis.observability import get_logger
from jarvis.voice.audio import input_device_index

log = get_logger(__name__)

_SAMPLE_RATE = 16000
_FRAME_MS = 30  # VAD frame size
_FRAME_SAMPLES = int(_SAMPLE_RATE * _FRAME_MS / 1000)


class SpeechRecognizer:
    def __init__(self) -> None:
        self._model = None
        self._vad = None

    def _load(self) -> None:
        if self._model is None:
            from faster_whisper import WhisperModel

            self._model = WhisperModel(
                settings.whisper_model,
                device=settings.whisper_device,
                compute_type="int8" if settings.whisper_device == "cpu" else "float16",
            )
            log.info("Whisper loaded: {} ({})", settings.whisper_model, settings.whisper_device)
        if self._vad is None:
            import webrtcvad

            self._vad = webrtcvad.Vad(2)  # aggressiveness 0–3
            log.info("WebRTC VAD ready")

    def record_utterance(
        self,
        max_seconds: float = 20.0,
        silence_ms: int = 900,
        preroll_ms: int = 300,
    ) -> np.ndarray:
        """Record from mic until user stops talking (or max_seconds). Returns int16 PCM."""
        self._load()
        import sounddevice as sd

        dev = input_device_index()
        stream = sd.InputStream(
            samplerate=_SAMPLE_RATE,
            channels=1,
            dtype="int16",
            blocksize=_FRAME_SAMPLES,
            device=dev,
        )
        stream.start()

        frames: list[np.ndarray] = []
        preroll = collections.deque(
            maxlen=int(preroll_ms / _FRAME_MS)
        )  # small lookback so we don't clip first phoneme
        silent_frames_needed = int(silence_ms / _FRAME_MS)
        silent_count = 0
        speech_started = False
        start_t = time.monotonic()

        try:
            while True:
                if time.monotonic() - start_t > max_seconds:
                    log.warning("STT: max utterance length reached")
                    break
                data, _ = stream.read(_FRAME_SAMPLES)
                frame = data[:, 0] if data.ndim > 1 else data
                raw_bytes = frame.tobytes()
                is_speech = self._vad.is_speech(raw_bytes, _SAMPLE_RATE)  # type: ignore[union-attr]

                if not speech_started:
                    preroll.append(frame.copy())
                    if is_speech:
                        speech_started = True
                        frames.extend(list(preroll))
                        frames.append(frame.copy())
                else:
                    frames.append(frame.copy())
                    if is_speech:
                        silent_count = 0
                    else:
                        silent_count += 1
                        if silent_count >= silent_frames_needed:
                            break
        finally:
            stream.stop()
            stream.close()

        if not frames:
            return np.zeros(0, dtype=np.int16)
        return np.concatenate(frames).astype(np.int16)

    def transcribe(self, pcm_int16: np.ndarray) -> str:
        if pcm_int16.size == 0:
            return ""
        self._load()
        audio_f32 = pcm_int16.astype(np.float32) / 32768.0
        segments, _info = self._model.transcribe(  # type: ignore[union-attr]
            audio_f32,
            language="en",
            vad_filter=False,
            beam_size=1,
        )
        text = " ".join(seg.text.strip() for seg in segments).strip()
        log.info("STT: {}", text)
        return text

    def record_and_transcribe(self, **kwargs) -> str:  # noqa: ANN003
        pcm = self.record_utterance(**kwargs)
        return self.transcribe(pcm)
