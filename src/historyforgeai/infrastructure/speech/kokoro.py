"""Local Kokoro ONNX speech synthesis (optional dependency)."""
import os
from pathlib import Path


class KokoroSpeech:
    def __init__(self, model=None, voices=None, voice=None, lang=None, speed=None, sentence_pause=None):
        self.model = Path(model or os.getenv("KOKORO_MODEL", "models/kokoro-v1.0.onnx")).expanduser()
        self.voices = Path(voices or os.getenv("KOKORO_VOICES", "models/voices-v1.0.bin")).expanduser()
        self.voice = voice or os.getenv("KOKORO_VOICE", "hm_omega")
        self.lang = lang or os.getenv("KOKORO_LANG", "hi")
        self.speed = float(speed or os.getenv("KOKORO_SPEED", "0.9"))
        self.sentence_pause = sentence_pause
        self._engine = None

    def synthesize(self, text: str, destination: str) -> bool:
        if not self.model.is_file() or not self.voices.is_file():
            raise RuntimeError("Kokoro model/voices missing; configure KOKORO_MODEL and KOKORO_VOICES")
        try:
            from kokoro_onnx import Kokoro
            import soundfile as sf
        except ImportError as exc:
            raise RuntimeError("Install Kokoro dependencies: pip install '.[kokoro]'") from exc
        if self._engine is None:
            self._engine = Kokoro(str(self.model), str(self.voices))
        kwargs = {"voice": self.voice, "speed": self.speed, "lang": self.lang}
        if self.sentence_pause is not None:
            kwargs["sentence_pause"] = self.sentence_pause
        samples, rate = self._engine.create(text, **kwargs)
        output = Path(destination)
        output.parent.mkdir(parents=True, exist_ok=True)
        sf.write(str(output), samples, rate)
        return output.is_file() and output.stat().st_size > 44
