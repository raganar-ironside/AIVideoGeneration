from historyforgeai.config import ROOT, settings
from historyforgeai.infrastructure.llm.compatible import CompatibleLLM
from historyforgeai.infrastructure.llm.mock import MockLLM
from historyforgeai.infrastructure.llm.gemini import GeminiLLM
from historyforgeai.infrastructure.llm.ollama import OllamaLLM
from historyforgeai.infrastructure.research.wikipedia import WikipediaResearch
from historyforgeai.infrastructure.assets.wikimedia import WikimediaAssets
from historyforgeai.infrastructure.speech.espeak import EspeakSpeech
from historyforgeai.infrastructure.rendering.ffmpeg import FFmpegRenderer
from historyforgeai.infrastructure.persistence.filesystem import FileJobRepository
from historyforgeai.application.pipeline import ShortsPipeline

def build(provider="mock", workspace=None, model=None):
    config = settings()
    providers = {"mock": MockLLM, "gemini": GeminiLLM, "ollama": OllamaLLM}
    if provider not in providers and provider not in ("groq", "openrouter", "openai"):
        raise ValueError(f"Unsupported provider: {provider}")
    work = workspace or (ROOT / "workspace")
    repo = FileJobRepository(work / "jobs")
    renderer = FFmpegRenderer(config["width"], config["height"], config["fps"])
    llm = CompatibleLLM(provider, model) if provider in ("groq", "openrouter", "openai") else providers[provider]()
    return ShortsPipeline(repo, llm, WikipediaResearch(), WikimediaAssets(),
                          EspeakSpeech(), renderer, work)
