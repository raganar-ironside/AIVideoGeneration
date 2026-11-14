"""Illustrated cutout preparation: all API calls are mocked and require consent."""
import base64
import io
import json
from pathlib import Path
from unittest.mock import patch

import pytest
from PIL import Image

from historyforgeai.application.services.illustrated_assets import (
    _openai_image, approve_scene_assets, load_asset_draft, prepare_scene_assets,
    reject_scene_assets, verify_approved_assets, update_approved_scene_spec,
)
from historyforgeai.application.services.storyboard import Shot, Storyboard, load, save
from historyforgeai.infrastructure.rendering.blender_2d import CutoutScene, build_blender_scene
from historyforgeai.domain.models import Scene


def png(transparent=True):
    output = io.BytesIO()
    image = Image.new("RGBA" if transparent else "RGB", (60, 90),
                      (150, 80, 30, 0) if transparent else (150, 80, 30))
    if transparent:
        for x in range(10, 50):
            for y in range(10, 80):
                image.putpixel((x, y), (150, 80, 30, 255))
    image.save(output, "PNG")
    return output.getvalue()


@pytest.fixture
def job(tmp_path):
    path = tmp_path / "workspace" / "jobs" / "demo"
    path.mkdir(parents=True)
    save(path / "storyboard.json", Storyboard(topic="Maurya", shots=[
        Shot(scene_index=1, narration="Chandragupta raises his sword",
             visual_description="Commander in front of fortress", search_query="fortress"),
        Shot(scene_index=2, narration="An army marches",
             visual_description="Army marching", search_query="army"),
    ]))
    Image.new("RGB", (72, 128), "#a47b51").save(path / "fort.jpg")
    return path


def test_manual_whole_stages_without_changing_live_scene(job, tmp_path):
    reference = tmp_path / "hero.png"
    reference.write_bytes(png())
    draft = prepare_scene_assets(job, 1, source=reference)
    assert draft.status == "pending_review"
    assert draft.mode == "whole"
    assert not (job / "animation" / "scene_01.json").exists()
    assert not (job / "animation" / "approved" / "scene_01.json").exists()
    assert load(job / "storyboard.json").shots[0].status == "pending_review"
    assert load_asset_draft(job, 1).hashes == draft.hashes


def test_approve_creates_real_blender_spec_and_detects_tampering(job, tmp_path):
    reference = tmp_path / "hero.png"
    reference.write_bytes(png())
    prepare_scene_assets(job, 1, source=reference)
    spec_path = approve_scene_assets(job, 1)
    assert spec_path.is_file()
    assert load_asset_draft(job, 1).status == "approved"
    assert CutoutScene.model_validate_json(spec_path.read_text()).layers[0].id == "character"
    verify_approved_assets(job, 1)
    scene = Scene(index=1, duration_seconds=4, narration="Test",
                  visual_description="Fort", asset_query="fort",
                  image_path=str(job / "fort.jpg"))
    payload = build_blender_scene(job, scene, 720, 1280, 24)
    assert len(payload["layers"]) == 2
    assert payload["frames"] == 96
    spec_path.write_text(spec_path.read_text() + "\n")
    with pytest.raises(ValueError, match="changed after approval"):
        verify_approved_assets(job, 1)


def test_manual_body_arm_uses_two_separate_transparent_assets(job, tmp_path):
    body = tmp_path / "body.png"
    arm = tmp_path / "arm.png"
    body.write_bytes(png())
    arm.write_bytes(png())
    draft = prepare_scene_assets(job, 1, mode="body-arm", source=body, arm_source=arm)
    assert set(draft.files) == {"body", "arm"}
    spec = CutoutScene.model_validate_json(approve_scene_assets(job, 1).read_text())
    assert [layer.id for layer in spec.layers] == ["character_body", "sword_arm"]
    assert spec.layers[1].pivot == (0.18, 0.12)
    verify_approved_assets(job, 1)
    (job / "animation" / "assets" / "scene_01" / "arm.png").write_bytes(png(False))
    with pytest.raises(ValueError, match="changed after approval"):
        verify_approved_assets(job, 1)


def test_reject_keeps_existing_live_approved_assets(job, tmp_path):
    source = tmp_path / "hero.png"
    source.write_bytes(png())
    prepare_scene_assets(job, 1, source=source)
    original_spec = approve_scene_assets(job, 1).read_bytes()
    prepare_scene_assets(job, 1, source=source, replace_draft=True)
    reject_scene_assets(job, 1)
    assert load_asset_draft(job, 1).status == "rejected"
    assert (job / "animation" / "scene_01.json").read_bytes() == original_spec
    verify_approved_assets(job, 1)


def test_opaque_image_is_rejected_without_background_removal(job, tmp_path):
    source = tmp_path / "opaque.png"
    source.write_bytes(png(False))
    with pytest.raises(ValueError, match="opaque"):
        prepare_scene_assets(job, 1, source=source)
    assert load_asset_draft(job, 1) is None


def test_paid_guard_prevents_network_calls(job):
    with patch("historyforgeai.application.services.illustrated_assets.requests.post") as post:
        with pytest.raises(ValueError, match="allow-paid"):
            prepare_scene_assets(job, 1, provider="openai")
        post.assert_not_called()


def test_manual_mode_needs_source_and_arm(job, tmp_path):
    with pytest.raises(ValueError, match="--source"):
        prepare_scene_assets(job, 1)
    source = tmp_path / "body.png"
    source.write_bytes(png())
    with pytest.raises(ValueError, match="--arm-source"):
        prepare_scene_assets(job, 1, mode="body-arm", source=source)


def test_ai_body_arm_generates_reference_then_two_edits(job):
    calls = []

    def generate(prompt, reference, transparent, model):
        calls.append((prompt, reference, transparent, model))
        return png()

    draft = prepare_scene_assets(job, 1, provider="openai", mode="body-arm",
                                 allow_paid=True, generator=generate)
    assert len(calls) == 3
    assert calls[0][1] is None
    assert calls[1][1].name == "reference.png"
    assert calls[2][1].name == "reference.png"
    assert set(draft.files) == {"body", "arm"}
    assert draft.status == "pending_review"


def test_ai_whole_creates_pending_illustration_and_background(job):
    def generate(prompt, reference, transparent, model):
        return png(transparent)

    draft = prepare_scene_assets(job, 1, provider="openai", allow_paid=True,
                                 generate_background=True, generator=generate)
    assert draft.background_candidate is not None
    assert Path(draft.background_candidate).is_file()
    shot = load(job / "storyboard.json").shots[0]
    assert shot.status == "pending_review"
    assert shot.candidate_image == draft.background_candidate
    assert load_asset_draft(job, 1).status == "pending_review"


def test_regeneration_needs_explicit_replace(job, tmp_path):
    source = tmp_path / "hero.png"
    source.write_bytes(png())
    prepare_scene_assets(job, 1, source=source)
    with pytest.raises(FileExistsError, match="--replace-draft"):
        prepare_scene_assets(job, 1, source=source)


def test_missing_scene_is_rejected_before_api(job):
    with pytest.raises(ValueError, match="not found"):
        prepare_scene_assets(job, 9, provider="openai", allow_paid=True,
                             generator=lambda *args: pytest.fail("must not generate"))


def test_openai_generations_use_transparency_and_b64(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            pass
        def json(self):
            return {"data": [{"b64_json": base64.b64encode(png()).decode()}]}
    requests = []
    def post(url, **kwargs):
        requests.append((url, kwargs))
        return FakeResponse()
    monkeypatch.setenv("OPENAI_API_KEY", "dummy-test-key")
    monkeypatch.setattr("historyforgeai.application.services.illustrated_assets.requests.post", post)
    assert _openai_image("Historical figure", None, True) == png()
    assert requests[0][0].endswith("/images/generations")
    assert requests[0][1]["json"]["background"] == "transparent"
    assert requests[0][1]["json"]["output_format"] == "png"


def test_openai_reference_edit_uses_multipart(monkeypatch, tmp_path):
    reference = tmp_path / "ref.png"
    reference.write_bytes(png())
    class FakeResponse:
        def raise_for_status(self):
            pass
        def json(self):
            return {"data": [{"b64_json": base64.b64encode(png()).decode()}]}
    calls = []
    def post(url, **kwargs):
        calls.append((url, kwargs))
        return FakeResponse()
    monkeypatch.setenv("OPENAI_API_KEY", "dummy-test-key")
    monkeypatch.setattr("historyforgeai.application.services.illustrated_assets.requests.post", post)
    _openai_image("Keep costume", reference, True)
    assert calls[0][0].endswith("/images/edits")
    assert "image" in calls[0][1]["files"]
    assert calls[0][1]["data"]["background"] == "transparent"


def test_reviewed_keyframe_edit_updates_approval_without_changing_art(job, tmp_path):
    source = tmp_path / "hero.png"
    source.write_bytes(png())
    prepare_scene_assets(job, 1, source=source)
    spec_path = approve_scene_assets(job, 1)
    spec = json.loads(spec_path.read_text())
    spec["layers"][0]["keyframes"][-1]["x"] = 0.61
    update_approved_scene_spec(job, 1, json.dumps(spec))
    verify_approved_assets(job, 1)
    assert json.loads(spec_path.read_text())["layers"][0]["keyframes"][-1]["x"] == 0.61
    spec["layers"][0]["asset"] = "../outside.png"
    with pytest.raises((ValueError, FileNotFoundError)):
        update_approved_scene_spec(job, 1, json.dumps(spec))
    verify_approved_assets(job, 1)


def test_keyframe_editor_requires_approved_assets(job):
    with pytest.raises(ValueError, match="Approve cutout"):
        update_approved_scene_spec(job, 1, '{"layers": []}')
