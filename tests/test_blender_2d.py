"""Blender cutout renderer tests; no Blender installation needed for validation.

The integration test uses FFmpeg to stand in for Blender and verifies frame
counts and output compatibility with the existing narration timeline.
"""
import json
import shutil
import subprocess
from pathlib import Path

import pytest
from PIL import Image
from pydantic import ValidationError

from historyforgeai.domain.models import Scene, ShortPlan
from historyforgeai.infrastructure.rendering import blender_2d
from historyforgeai.infrastructure.rendering.blender_2d import (
    Blender2DRenderer, CutoutScene, build_blender_scene, resolve_cutout_asset,
)


def make_job(tmp_path, count=1):
    job = tmp_path / "workspace" / "jobs" / "test-job"
    job.mkdir(parents=True)
    background = job / "background.jpg"
    Image.new("RGB", (72, 128), "#38516c").save(background)
    scenes = [
        Scene(index=i, duration_seconds=0.5, narration=f"Scene {i}",
              visual_description="Fort", asset_query="fort", image_path=str(background))
        for i in range(1, count + 1)
    ]
    plan = ShortPlan(topic="Demo", title="Demo", narration=" ".join(s.narration for s in scenes),
                     scenes=scenes)
    return job, plan


def make_transparent_png(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", (30, 40), (240, 130, 50, 180)).save(path)


def test_default_scene_uses_approved_image_and_audio_aligned_frames(tmp_path):
    job, plan = make_job(tmp_path)
    payload = build_blender_scene(job, plan.scenes[0], 720, 1280, 24)
    assert payload["frames"] == 12
    assert payload["layers"][0]["fit"] == "cover"
    assert payload["layers"][0]["asset"] == str(job / "background.jpg")


def test_cutout_scene_accepts_independently_rotating_arm(tmp_path):
    job, plan = make_job(tmp_path)
    arm = job / "animation" / "assets" / "arm.png"
    make_transparent_png(arm)
    (job / "animation" / "scene_01.json").write_text(json.dumps({
        "layers": [{
            "id": "sword_arm", "asset": "animation/assets/arm.png",
            "x": 0.6, "y": 0.5, "width": 0.2, "pivot": [0.2, 0.1],
            "z": 2, "keyframes": [
                {"t": 0, "rotation_deg": -35},
                {"t": 0.4, "rotation_deg": 70},
            ],
        }]
    }))
    payload = build_blender_scene(job, plan.scenes[0], 720, 1280, 24)
    assert len(payload["layers"]) == 2
    assert payload["layers"][1]["asset"] == str(arm)
    assert payload["layers"][1]["pivot"] == (0.2, 0.1)
    assert payload["layers"][1]["keyframes"][1]["rotation_deg"] == 70


@pytest.mark.parametrize("path", ["../outside.png", "/tmp/outside.png",
                                  "library:../outside.png", "library:/etc/passwd"])
def test_asset_paths_cannot_escape_allowed_roots(tmp_path, path):
    job, _ = make_job(tmp_path)
    with pytest.raises(ValueError):
        resolve_cutout_asset(job, path)


def test_symlink_outside_workspace_is_rejected(tmp_path):
    job, _ = make_job(tmp_path)
    outside = tmp_path / "outside.png"
    make_transparent_png(outside)
    link = job / "arm.png"
    link.symlink_to(outside)
    with pytest.raises(ValueError):
        resolve_cutout_asset(job, "arm.png")


def test_opaque_cutout_is_rejected(tmp_path):
    job, _ = make_job(tmp_path)
    Image.new("RGB", (30, 40), "white").save(job / "opaque.png")
    with pytest.raises(ValueError, match="transparency"):
        resolve_cutout_asset(job, "opaque.png")


def test_reusable_workspace_character_asset(tmp_path):
    job, _ = make_job(tmp_path)
    asset = job.parent.parent / "characters" / "chandragupta" / "arm.png"
    make_transparent_png(asset)
    assert resolve_cutout_asset(job, "library:characters/chandragupta/arm.png") == asset


def test_invalid_animation_keyframes_fail_closed():
    with pytest.raises(ValidationError, match="unique, increasing"):
        CutoutScene.model_validate({"layers": [{
            "id": "arm", "asset": "arm.png",
            "keyframes": [{"t": 0.7, "rotation_deg": 20},
                          {"t": 0.2, "rotation_deg": 30}],
        }]})
    with pytest.raises(ValidationError, match="unique"):
        CutoutScene.model_validate({"layers": [
            {"id": "arm", "asset": "a.png"}, {"id": "arm", "asset": "b.png"},
        ]})


def test_missing_blender_explains_install(tmp_path, monkeypatch):
    job, plan = make_job(tmp_path)
    monkeypatch.setattr(blender_2d.shutil, "which", lambda name: None if name == "blender" else "/usr/bin/" + name)
    with pytest.raises(RuntimeError, match="Blender is required"):
        Blender2DRenderer().render(plan, str(job))


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"),
                    reason="FFmpeg and FFprobe needed for integration test")
def test_blender_mode_preserves_scene_frames_and_existing_output_contract(tmp_path, monkeypatch):
    job, plan = make_job(tmp_path, count=2)
    real_run = subprocess.run
    real_which = shutil.which
    monkeypatch.setattr(blender_2d.shutil, "which",
                        lambda name: "/fake/blender" if name == "blender" else real_which(name))

    def fake_blender(cmd, **kwargs):
        if cmd[0] == "/fake/blender":
            payload = json.loads(Path(cmd[-2]).read_text(encoding="utf-8"))
            return real_run(
                ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                 "-f", "lavfi", "-i",
                 f"color=c=blue:s={payload['width']}x{payload['height']}:r={payload['fps']}",
                 "-frames:v", str(payload["frames"]), "-c:v", "libx264",
                 "-preset", "ultrafast", "-pix_fmt", "yuv420p", cmd[-1]],
                check=True, timeout=30,
            )
        return real_run(cmd, **kwargs)

    monkeypatch.setattr(blender_2d.subprocess, "run", fake_blender)
    renderer = Blender2DRenderer(width=72, height=128, fps=24)
    output = renderer.render(plan, str(job), motion="static")
    assert Path(output) == job / "short.mp4"
    assert blender_2d._frame_count(job / "clips" / "scene_01.mp4") == 12
    assert blender_2d._frame_count(job / "clips" / "scene_02.mp4") == 12
    assert blender_2d._frame_count(Path(output)) == 24
