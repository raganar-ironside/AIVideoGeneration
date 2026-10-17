"""OpenAI-compatible chat completions for Groq, OpenRouter and OpenAI."""
import os
import requests
from historyforgeai.domain.models import ShortPlan
from historyforgeai.infrastructure.llm.prompt import build_prompt

PROVIDERS = {
    "groq": ("GROQ_API_KEY", "https://api.groq.com/openai/v1/chat/completions", "openai/gpt-oss-120b"),
    "openrouter": ("OPENROUTER_API_KEY", "https://openrouter.ai/api/v1/chat/completions", "openrouter/free"),
    "openai": ("OPENAI_API_KEY", "https://api.openai.com/v1/chat/completions", "gpt-4.1-mini"),
}


class CompatibleLLM:
    def __init__(self, provider: str, model: str | None = None):
        if provider not in PROVIDERS:
            raise ValueError(f"Unsupported compatible provider: {provider}")
        self.provider = provider
        self.model = model

    def create_plan(self, topic: str, context: str, duration: int, scenes: int) -> ShortPlan:
        key_env, url, default_model = PROVIDERS[self.provider]
        key = os.getenv(key_env)
        if not key:
            raise RuntimeError(f"Set {key_env} in .env")
        model = self.model or os.getenv(f"{self.provider.upper()}_MODEL", default_model)
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": "Return only valid JSON matching the requested structure."},
                {"role": "user", "content": build_prompt(topic, context, duration, scenes)},
            ],
            "temperature": 0.3,
        }
        response = requests.post(url, headers={"Authorization": f"Bearer {key}"},
                                 json=payload, timeout=120)
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        return ShortPlan.model_validate_json(content)
