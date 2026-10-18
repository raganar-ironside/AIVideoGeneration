import wave

import pytest

from historyforgeai.infrastructure.speech.gemini import GeminiSpeech


def test_missing_api_key_fails(monkeypatch, tmp_path):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    # Dependency import may fail first when optional extra is not installed.
    with pytest.raises(RuntimeError):
        GeminiSpeech().synthesize("नमस्ते", str(tmp_path / "sample.wav"))


def test_gemini_provider_factory(monkeypatch):
    monkeypatch.setenv("SPEECH_PROVIDER", "gemini")
    from historyforgeai.infrastructure.speech.factory import build_speech
    speech = build_speech()
    assert speech.providers[0][0] == "gemini"
