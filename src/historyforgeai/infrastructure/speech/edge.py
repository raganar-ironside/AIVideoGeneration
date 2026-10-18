"""Online Edge TTS adapter; transcodes its MP3 output to WAV."""
import asyncio
import os
import subprocess
import tempfile
from pathlib import Path


class EdgeSpeech:
    def __init__(self, voice=None, rate=None, pitch=None, volume=None):
        self.voice = voice or os.getenv("EDGE_TTS_VOICE", "hi-IN-MadhurNeural")
        self.rate = rate or os.getenv("EDGE_TTS_RATE", "-8%")
        self.pitch = pitch if pitch is not None else os.getenv("EDGE_TTS_PITCH", "+0Hz")
        self.volume = volume if volume is not None else os.getenv("EDGE_TTS_VOLUME", "+0%")

    def synthesize(self, text: str, destination: str) -> bool:
        try:
            import edge_tts
        except ImportError as exc:
            raise RuntimeError("Install Edge TTS dependency: pip install '.[edge]'") from exc
        output = Path(destination)
        output.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory() as temp:
            mp3 = Path(temp) / "edge.mp3"

            async def run():
                await edge_tts.Communicate(text, self.voice, rate=self.rate, pitch=self.pitch, volume=self.volume).save(str(mp3))

            asyncio.run(run())
            subprocess.run(
                ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(mp3),
                 "-ar", "24000", "-ac", "1", str(output)],
                check=True, capture_output=True, timeout=120,
            )
        return output.is_file() and output.stat().st_size > 44
