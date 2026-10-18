"""Configure speech provider priority using environment variables."""
import os

from dotenv import load_dotenv
from historyforgeai.config import ROOT

from historyforgeai.infrastructure.speech.espeak import EspeakSpeech
from historyforgeai.infrastructure.speech.edge import EdgeSpeech
from historyforgeai.infrastructure.speech.gemini import GeminiSpeech
from historyforgeai.infrastructure.speech.kokoro import KokoroSpeech
from historyforgeai.infrastructure.speech.fallback import FallbackSpeech
from historyforgeai.infrastructure.speech.presets import MasteredSpeech, selected_preset


def build_speech():
    load_dotenv(ROOT / ".env")
    mode = os.getenv("SPEECH_PROVIDER", "espeak").strip().lower()
    names = (os.getenv("SPEECH_FALLBACK_ORDER", "kokoro,edge,espeak") if mode == "auto" else mode)
    order = [item.strip().lower() for item in names.split(",") if item.strip()]
    if not order or any(name not in {"kokoro", "edge", "espeak", "gemini"} for name in order):
        raise ValueError("SPEECH_PROVIDER must be auto, kokoro, edge, gemini, or espeak")
    preset = selected_preset()
    providers = []
    for name in dict.fromkeys(order):
        if name == "kokoro":
            provider = KokoroSpeech(speed=preset.speed, sentence_pause=preset.sentence_pause)
        elif name == "gemini":
            provider = GeminiSpeech()
        elif name == "edge":
            provider = EdgeSpeech(rate=f"{round((preset.speed - 1) * 100):+d}%")
        else:
            provider = EspeakSpeech()
        providers.append((name, provider))
    return MasteredSpeech(FallbackSpeech(providers), preset)
