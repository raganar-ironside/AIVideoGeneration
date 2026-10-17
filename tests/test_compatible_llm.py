from unittest.mock import patch, Mock
import pytest
from historyforgeai.infrastructure.llm.compatible import CompatibleLLM


def test_missing_api_key(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="GROQ_API_KEY"):
        CompatibleLLM("groq").create_plan("topic", "context", 60, 2)


def test_groq_request_and_validation(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "dummy-test-key")
    response = Mock()
    response.json.return_value = {"choices": [{"message": {"content": """{
      "topic": "Example", "title": "Example", "narration": "One. Two.",
      "scenes": [
        {"index": 1, "duration_seconds": 30, "narration": "One.", "visual_description": "A", "asset_query": "A"},
        {"index": 2, "duration_seconds": 30, "narration": "Two.", "visual_description": "B", "asset_query": "B"}
      ]
    }"""}}]}
    with patch("historyforgeai.infrastructure.llm.compatible.requests.post", return_value=response) as post:
        plan = CompatibleLLM("groq").create_plan("Example", "context", 60, 2)
    assert len(plan.scenes) == 2
    assert post.call_args.kwargs["json"]["model"] == "openai/gpt-oss-120b"


def test_invalid_provider():
    with pytest.raises(ValueError):
        CompatibleLLM("unknown")
