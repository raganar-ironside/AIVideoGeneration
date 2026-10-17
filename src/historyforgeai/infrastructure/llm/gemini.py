import os
import requests
from historyforgeai.domain.models import ShortPlan
from historyforgeai.infrastructure.llm.prompt import build_prompt

class GeminiLLM:
    def create_plan(self, topic: str, context: str, duration: int, scenes: int) -> ShortPlan:
        key = os.getenv("GEMINI_API_KEY")
        if not key:
            raise RuntimeError("Set GEMINI_API_KEY in .env")
        model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        payload = {"contents": [{"parts": [{"text": build_prompt(topic, context, duration, scenes)}]}],
                   "generationConfig": {"responseMimeType": "application/json", "temperature": 0.3}}
        response = requests.post(url, headers={"x-goog-api-key": key}, json=payload, timeout=120)
        response.raise_for_status()
        result = response.json()
        content = result["candidates"][0]["content"]["parts"][0]["text"]
        return ShortPlan.model_validate_json(content)
