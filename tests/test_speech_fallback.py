from pathlib import Path
import pytest
from historyforgeai.infrastructure.speech.fallback import FallbackSpeech
from historyforgeai.infrastructure.speech.factory import build_speech


class Broken:
    def synthesize(self, text, destination):
        Path(destination).write_bytes(b"partial")
        raise RuntimeError("offline")


class Good:
    def synthesize(self, text, destination):
        Path(destination).write_bytes(b"RIFF" + b"x" * 100)
        return True


def test_fallback_removes_partial_audio(tmp_path):
    path = tmp_path / "speech.wav"
    assert FallbackSpeech([("broken", Broken()), ("good", Good())]).synthesize("hello", str(path))
    assert path.stat().st_size > 44


def test_all_failures_are_reported(tmp_path):
    with pytest.raises(RuntimeError, match="broken"):
        FallbackSpeech([("broken", Broken())]).synthesize("hello", str(tmp_path / "speech.wav"))


def test_default_preserves_espeak(monkeypatch):
    monkeypatch.setenv("SPEECH_PROVIDER", "espeak")
    assert build_speech().providers[0][0] == "espeak"


def test_auto_priority(monkeypatch):
    monkeypatch.setenv("SPEECH_PROVIDER", "auto")
    monkeypatch.setenv("SPEECH_FALLBACK_ORDER", "kokoro,edge,espeak")
    assert [name for name, _ in build_speech().providers] == ["kokoro", "edge", "espeak"]
