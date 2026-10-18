"""Unit tests for voice presets and provider wiring."""
import pytest

from historyforgeai.infrastructure.speech.presets import PRESETS, selected_preset


@pytest.fixture(autouse=True)
def clear_voice_overrides(monkeypatch):
    for name in ("VOICE_SPEED", "VOICE_PITCH_SEMITONES", "VOICE_BASS_DB", "VOICE_SENTENCE_PAUSE"):
        monkeypatch.delenv(name, raising=False)


def test_default_preset(monkeypatch):
    monkeypatch.delenv("VOICE_PRESET", raising=False)
    assert selected_preset() == PRESETS["normal"]


def test_documentary_preset(monkeypatch):
    monkeypatch.setenv("VOICE_PRESET", "documentary")
    assert selected_preset().pitch == -1.5
    assert selected_preset().speed == 0.9


def test_override(monkeypatch):
    monkeypatch.setenv("VOICE_PRESET", "epic")
    monkeypatch.setenv("VOICE_PITCH_SEMITONES", "-3")
    assert selected_preset().pitch == -3


def test_invalid_preset(monkeypatch):
    monkeypatch.setenv("VOICE_PRESET", "unknown")
    with pytest.raises(ValueError):
        selected_preset()
