from jarvis.config import settings


def test_settings_load_defaults() -> None:
    assert settings.jarvis_name
    assert settings.whisper_model
    assert settings.audio_sample_rate > 0
    assert 0.0 <= settings.wake_word_threshold <= 1.0
