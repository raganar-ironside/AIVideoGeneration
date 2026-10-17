import os
import requests
from historyforgeai.domain.models import ShortPlan
from historyforgeai.infrastructure.llm.prompt import build_prompt

class OllamaLLM:
    def create_plan(self, topic: str, context: str, duration: int, scenes: int) -> ShortPlan:
        url = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
        payload = {"model": os.getenv("OLLAMA_MODEL", "llama3.2:3b"),
                   "prompt": build_prompt(topic, context, duration, scenes),
                   "format": ShortPlan.model_json_schema(), "stream": False,
                   "options": {"temperature": 0.3}}
        response = requests.post(url, json=payload, timeout=300)
        response.raise_for_status()
        return ShortPlan.model_validate_json(response.json()["response"])
