"""Smoke tests for the generic controller. Doesn't actually launch anything."""

from jarvis.control.generic import GenericController
from jarvis.control.windows import _looks_like_url


def test_url_detection() -> None:
    assert _looks_like_url("https://openai.com")
    assert _looks_like_url("www.google.com")
    assert _looks_like_url("github.com/foo")
    assert not _looks_like_url("how old is the moon")


def test_generic_controller_returns_shape() -> None:
    c = GenericController()
    # media_key should return the documented {ok, error} shape on Linux/macOS
    res = c.media_key("play_pause")
    assert "ok" in res
