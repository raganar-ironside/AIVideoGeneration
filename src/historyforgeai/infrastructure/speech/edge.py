import asyncio
from pathlib import Path

class EdgeSpeech:
    """Optional online adapter using the unofficial edge-tts service."""
    def __init__(self, voice='hi-IN-MadhurNeural', rate='-8%'):
        self.voice, self.rate = voice, rate

    def synthesize(self, text: str, destination: str) -> bool:
        try:
            import edge_tts
        except ImportError as exc:
            raise RuntimeError('Install optional speech dependency: pip install edge-tts') from exc
        Path(destination).parent.mkdir(parents=True, exist_ok=True)
        async def run():
            await edge_tts.Communicate(text, self.voice, rate=self.rate).save(destination)
        asyncio.run(run())
        return Path(destination).stat().st_size > 0
