"""Configure speech provider priority using environment variables."""
import os

from dotenv import load_dotenv
from historyforgeai.config import ROOT

from historyforgeai.infrastructure.speech.espeak import EspeakSpeech
from historyforgeai.infrastructure.speech.edge import EdgeSpeech
from historyforgeai.infrastructure.speech.kokoro import KokoroSpeech
from historyforgeai.infrastructure.speech.fallback import FallbackSpeech


def build_speech():
    load_dotenv(ROOT / ".env")
    mode = os.getenv("SPEECH_PROVIDER", "espeak").strip().lower()
    names = (os.getenv("SPEECH_FALLBACK_ORDER", "kokoro,edge,espeak") if mode == "auto" else mode)
    order = [item.strip().lower() for item in names.split(",") if item.strip()]
    if not order or any(name not in {"kokoro", "edge", "espeak"} for name in order):
        raise ValueError("SPEECH_PROVIDER must be auto, kokoro, edge, or espeak")
    constructors = {
        "kokoro": KokoroSpeech,
        "edge": EdgeSpeech,
        "espeak": EspeakSpeech,
    }
    return FallbackSpeech([(name, constructors[name]()) for name in dict.fromkeys(order)])
