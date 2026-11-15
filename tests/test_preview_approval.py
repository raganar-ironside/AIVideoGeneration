"""Preview approval must be bound to the exact generated video and inputs."""
import json
from types import SimpleNamespace

import pytest

from historyforgeai.application.services import preview_approval


def test_approval_rejects_stale_inputs(tmp_path):
    preview = tmp_path / "short_preview.mp4"
    preview.write_bytes(b"draft")
    (tmp_path / "preview_fingerprint.json").write_text(
        json.dumps({"fingerprint": "scene-a"}), encoding="utf-8"
    )
    preview_approval.approve_preview(tmp_path, "scene-a")
    assert preview_approval.is_preview_approved(tmp_path, "scene-a")
    assert not preview_approval.is_preview_approved(tmp_path, "scene-b")
    with pytest.raises(ValueError):
        preview_approval.approve_preview(tmp_path, "scene-b")


def test_approval_invalidated_by_preview_replacement(tmp_path):
    (tmp_path / "short_preview.mp4").write_bytes(b"first")
    (tmp_path / "preview_fingerprint.json").write_text(
        json.dumps({"fingerprint": "a"}), encoding="utf-8"
    )
    preview_approval.approve_preview(tmp_path, "a")
    (tmp_path / "short_preview.mp4").write_bytes(b"changed")
    assert not preview_approval.is_preview_approved(tmp_path, "a")


def test_fingerprint_changes_when_asset_changes(tmp_path, monkeypatch):
    image = tmp_path / "background.png"
    image.write_bytes(b"first")
    scene = SimpleNamespace(index=1)
    plan = SimpleNamespace(scenes=[scene])
    monkeypatch.setattr(preview_approval, "build_blender_scene",
                        lambda job, scene, w, h, fps: {
                            "background": str(image), "parts": [],
                            "frames": 144, "width": w, "height": h, "fps": fps,
                        })
    before = preview_approval.preview_fingerprint(tmp_path, plan)
    image.write_bytes(b"second")
    assert preview_approval.preview_fingerprint(tmp_path, plan) != before
