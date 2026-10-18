"""Configurable narration presets and FFmpeg mastering."""
import math
import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class VoicePreset:
    speed: float
    pitch: float
    bass: float
    sentence_pause: float


PRESETS = {
    "normal": VoicePreset(1.0, 0.0, 0.0, 0.2),
    "documentary": VoicePreset(0.9, -1.5, 2.0, 0.5),
    "epic": VoicePreset(0.95, -2.0, 3.0, 0.35),
}


def selected_preset() -> VoicePreset:
    name = os.getenv("VOICE_PRESET", "normal").strip().lower()
    if name not in PRESETS:
        raise ValueError(f"VOICE_PRESET must be one of: {', '.join(PRESETS)}")
    base = PRESETS[name]
    values = (
        float(os.getenv("VOICE_SPEED", base.speed)),
        float(os.getenv("VOICE_PITCH_SEMITONES", base.pitch)),
        float(os.getenv("VOICE_BASS_DB", base.bass)),
        float(os.getenv("VOICE_SENTENCE_PAUSE", base.sentence_pause)),
    )
    speed, pitch, bass, pause = values
    if not 0.5 <= speed <= 2.0:
        raise ValueError("VOICE_SPEED must be between 0.5 and 2.0")
    if not -6 <= pitch <= 6 or not -12 <= bass <= 12 or not 0 <= pause <= 3:
        raise ValueError("Voice pitch, bass, or sentence pause is out of range")
    return VoicePreset(*values)


class MasteredSpeech:
    """Master successful fallback audio without altering provider selection."""

    def __init__(self, speech, preset: VoicePreset):
        self.speech = speech
        self.preset = preset

    def synthesize(self, text: str, destination: str) -> bool:
        output = Path(destination)
        output.parent.mkdir(parents=True, exist_ok=True)
        # Keep the normal preset free of unnecessary transcoding.
        if self.preset.pitch == 0 and self.preset.bass == 0:
            return self.speech.synthesize(text, str(output))
        with tempfile.TemporaryDirectory() as temp:
            raw = Path(temp) / "raw.wav"
            if not self.speech.synthesize(text, str(raw)):
                return False
            pitch_factor = 2 ** (self.preset.pitch / 12)
            filters = []
            if not math.isclose(pitch_factor, 1.0):
                # asetrate shifts pitch and tempo; atempo restores duration.
                filters.extend([
                    f"asetrate=24000*{pitch_factor:.8f}",
                    "aresample=24000",
                    f"atempo={1 / pitch_factor:.8f}",
                ])
            if self.preset.bass:
                filters.append(f"equalizer=f=130:t=q:w=1:g={self.preset.bass:g}")
            filters.append("loudnorm=I=-16:TP=-1.5:LRA=11")
            try:
                subprocess.run(
                    ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                     "-i", str(raw), "-ar", "24000", "-ac", "1",
                     "-af", ",".join(filters), str(output)],
                    check=True, capture_output=True, timeout=120,
                )
                return output.is_file() and output.stat().st_size > 44
            except Exception:
                output.unlink(missing_ok=True)
                raise
