"""Gemini Nano Banana image API and per-job estimated budget tests.

All provider responses are mocked; no billed API calls occur in CI.
"""
import base64
import io
import json
from pathlib import Path

import pytest
from PIL import Image

from historyforgeai.application.services.image_api_budget import (
    job_budget_limit, preflight_image_budget, reserve_image_request, usage_summary,
)
from historyforgeai.application.services.illustrated_assets import (
    prepare_scene_assets, load_asset_draft,
)
from historyforgeai.application.services.storyboard import Shot, Storyboard, save
from historyforgeai.infrastructure.images.gemini_cutout import gemini_image


def _png(transparent=True):
    image = Image.new("RGBA" if transparent else "RGB", (48, 72),
                      (60, 30, 80, 0) if transparent else (60, 30, 80))
    if transparent:
        for x in range(8, 40):
            for y in range(8, 64):
                image.putpixel((x, y), (80, 120, 180, 255))
    buf = io.BytesIO()
    image.save(buf, "PNG")
    return buf.getvalue()


@pytest.fixture
def job(tmp_path):
    folder = tmp_path / "workspace" / "jobs" / "test-job"
    folder.mkdir(parents=True)
    save(folder / "storyboard.json", Storyboard(topic="Mauryan empire", shots=[
        Shot(scene_index=1, narration="The sword is raised",
             visual_description="Ancient Indian fortress", search_query="fortress"),
    ]))
    return folder


def test_gemini_generation_uses_image_modalities_and_decodes_image(monkeypatch):
    calls = []
    class Response:
        def raise_for_status(self):
            pass
        def json(self):
            return {"candidates": [{"content": {"parts": [
                {"text": "Here is the image"},
                {"inlineData": {"mimeType": "image/png",
                                "data": base64.b64encode(_png()).decode("ascii")}},
            ]}}]}
    def post(url, **kwargs):
        calls.append((url, kwargs))
        return Response()
    monkeypatch.setenv("GEMINI_API_KEY", "unit-test-key")
    monkeypatch.setattr("historyforgeai.infrastructure.images.gemini_cutout.requests.post", post)
    assert gemini_image("A historical king", None, True) == _png()
    url, kwargs = calls[0]
    assert url.endswith("/models/gemini-3.1-flash-image:generateContent")
    assert kwargs["headers"]["x-goog-api-key"] == "unit-test-key"
    assert kwargs["json"]["generationConfig"]["responseModalities"] == ["IMAGE"]
    assert len(kwargs["json"]["contents"][0]["parts"]) == 1


def test_gemini_reference_guided_edit_sends_inline_image(monkeypatch, tmp_path):
    image = tmp_path / "reference.png"
    image.write_bytes(_png())
    calls = []
    class Response:
        def raise_for_status(self):
            pass
        def json(self):
            return {"candidates": [{"content": {"parts": [
                {"inline_data": {"mime_type": "image/png",
                                 "data": base64.b64encode(_png()).decode("ascii")}},
            ]}}]}
    def post(url, **kwargs):
        calls.append(kwargs["json"])
        return Response()
    monkeypatch.setenv("GEMINI_API_KEY", "unit-test-key")
    monkeypatch.setattr("historyforgeai.infrastructure.images.gemini_cutout.requests.post", post)
    assert gemini_image("Keep the same armor", image, True, "gemini-2.5-flash-image") == _png()
    parts = calls[0]["contents"][0]["parts"]
    assert len(parts) == 2
    assert base64.b64decode(parts[1]["inline_data"]["data"]).startswith(b"\\x89PNG".replace(b"\\x89", bytes([137])))


def test_gemini_missing_key_fails_before_network(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        gemini_image("Test", None, True)


def test_gemini_rejects_text_only_response(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "unit-test-key")
    class Response:
        def raise_for_status(self):
            pass
        def json(self):
            return {"candidates": [{"content": {"parts": [{"text": "I cannot generate this"}]}}]}
    monkeypatch.setattr("historyforgeai.infrastructure.images.gemini_cutout.requests.post",
                        lambda *args, **kwargs: Response())
    with pytest.raises(ValueError, match="no image bytes"):
        gemini_image("Test", None, True)


def test_gemini_rejects_invalid_model(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "unit-test-key")
    with pytest.raises(ValueError, match="Invalid Gemini"):
        gemini_image("Test", None, True, "../../bad?key=leak")


def test_budget_preflight_and_reservations_are_persistent(job, monkeypatch):
    monkeypatch.setenv("GEMINI_IMAGE_ESTIMATED_USD", "0.25")
    preflight_image_budget(job, "gemini", 2, 0.50)
    reserve_image_request(job, "gemini", "gemini-3.1-flash-image", 0.50)
    reserve_image_request(job, "gemini", "gemini-3.1-flash-image", 0.50)
    with pytest.raises(ValueError, match="budget exceeded"):
        reserve_image_request(job, "gemini", "gemini-3.1-flash-image", 0.50)
    usage = usage_summary(job)
    assert usage["attempted_requests"] == 2
    assert usage["estimated_spend_usd"] == 0.50
    assert len(usage["requests"]) == 2


def test_budget_blocks_invalid_and_nonfinite_limits(job):
    with pytest.raises(ValueError, match="positive"):
        preflight_image_budget(job, "gemini", 1, float("nan"))
    with pytest.raises(ValueError, match="positive"):
        preflight_image_budget(job, "gemini", 1, 0)


def test_budget_limits_request_count_even_if_estimate_is_small(job, monkeypatch):
    monkeypatch.setenv("IMAGE_JOB_MAX_REQUESTS", "2")
    monkeypatch.setenv("GEMINI_IMAGE_ESTIMATED_USD", "0.01")
    preflight_image_budget(job, "gemini", 2, 1.0)
    with pytest.raises(ValueError, match="MAX_REQUESTS"):
        preflight_image_budget(job, "gemini", 3, 1.0)


def test_gemini_is_a_real_asset_preparation_provider(job):
    calls = []
    def fake_image(prompt, reference, transparent, model):
        calls.append((prompt, reference, transparent, model))
        return _png(transparent)
    draft = prepare_scene_assets(
        job, 1, provider="gemini", mode="whole", allow_paid=True,
        generate_background=True, image_budget_usd=0.5, generator=fake_image,
    )
    assert draft.provider == "gemini"
    assert draft.status == "pending_review"
    assert len(calls) == 2
    assert calls[0][3] == "gemini-3.1-flash-image"
    assert calls[1][2] is False
    assert usage_summary(job)["estimated_spend_usd"] == 0.50
    assert load_asset_draft(job, 1).background_candidate is not None


def test_gemini_budget_preflight_blocks_partial_generation(job):
    calls = []
    def fake_image(*args):
        calls.append(args)
        return _png()
    with pytest.raises(ValueError, match="budget exceeded"):
        prepare_scene_assets(
            job, 1, provider="gemini", mode="body-arm", allow_paid=True,
            image_budget_usd=0.5, generator=fake_image,
        )
    assert calls == []
    assert usage_summary(job)["attempted_requests"] == 0
    assert load_asset_draft(job, 1) is None


def test_gemini_requires_explicit_paid_consent(job):
    with pytest.raises(ValueError, match="allow-paid"):
        prepare_scene_assets(job, 1, provider="gemini")
    assert usage_summary(job)["attempted_requests"] == 0


def test_failed_api_attempt_is_counted_for_safety(job):
    def fail(*args):
        raise RuntimeError("Provider timeout")
    with pytest.raises(RuntimeError, match="Provider timeout"):
        prepare_scene_assets(
            job, 1, provider="gemini", allow_paid=True, generator=fail,
        )
    assert usage_summary(job)["attempted_requests"] == 1
    assert load_asset_draft(job, 1) is None
