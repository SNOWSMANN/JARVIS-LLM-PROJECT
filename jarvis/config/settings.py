"""Centralized configuration loaded from environment / .env."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All runtime configuration for Jarvis.

    Values are loaded, in order of precedence, from:
    1. Actual environment variables
    2. A local `.env` file at the repo root
    3. The defaults declared below
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- LLM ---
    openai_api_key: str = Field(default="")
    openai_model: str = Field(default="gpt-4o-mini")
    openai_model_fast: str = Field(default="gpt-4o-mini")

    ollama_base_url: str = Field(default="http://localhost:11434")
    ollama_model: str = Field(default="llama3.1:8b")
    ollama_enabled: bool = Field(default=False)

    # --- TTS ---
    elevenlabs_api_key: str = Field(default="")
    elevenlabs_voice_id: str = Field(default="pNInz6obpgDQGcFmaJgB")
    elevenlabs_model: str = Field(default="eleven_turbo_v2_5")
    tts_fallback: str = Field(default="pyttsx3")

    # --- STT ---
    whisper_model: str = Field(default="base.en")
    whisper_device: str = Field(default="cpu")

    # --- Wake word ---
    wake_word_model: str = Field(default="hey_jarvis")
    wake_word_threshold: float = Field(default=0.5)

    # --- Audio ---
    audio_input_device: str = Field(default="")
    audio_output_device: str = Field(default="")
    audio_sample_rate: int = Field(default=16000)

    # --- Memory ---
    database_url: str = Field(default="sqlite:///data/jarvis.db")
    chroma_persist_dir: str = Field(default="data/chroma_db")
    memory_short_term_window: int = Field(default=20)
    memory_importance_threshold: float = Field(default=0.35)

    # --- Identity ---
    jarvis_name: str = Field(default="Jarvis")
    jarvis_user_name: str = Field(default="Sir")
    jarvis_personality: str = Field(default="crisp_british_butler")

    # --- Server ---
    server_host: str = Field(default="127.0.0.1")
    server_port: int = Field(default=8765)
    server_api_key: str = Field(default="change-me")

    # --- Safety ---
    require_confirm_destructive: bool = Field(default=True)
    audit_log: bool = Field(default=True)

    # --- Logging ---
    log_level: str = Field(default="INFO")
    log_dir: str = Field(default="logs")

    @property
    def data_dir(self) -> Path:
        p = Path("data")
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def logs_path(self) -> Path:
        p = Path(self.log_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def has_openai(self) -> bool:
        return bool(self.openai_api_key and not self.openai_api_key.startswith("sk-REPLACE"))

    @property
    def has_elevenlabs(self) -> bool:
        return bool(self.elevenlabs_api_key and self.elevenlabs_api_key != "REPLACE_ME")


settings = Settings()
