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
    Blender2DRenderer, PuppetRig, build_blender_scene, resolve_cutout_asset,
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
    assert payload["version"] == 2
    assert payload["background"] == str(job / "background.jpg")
    assert payload["parts"] == []


def test_puppet_scene_builds_parented_arm_with_easing(tmp_path):
    job, plan = make_job(tmp_path)
    body = job / "animation" / "assets" / "body.png"
    arm = job / "animation" / "assets" / "arm.png"
    make_transparent_png(body)
    make_transparent_png(arm)
    (job / "animation" / "scene_01.json").write_text(json.dumps({
        "version": 2,
        "parts": [
            {"id": "torso", "asset": "animation/assets/body.png",
             "x": .5, "y": .65, "width": .5},
            {"id": "arm", "asset": "animation/assets/arm.png",
             "parent": "torso", "x": .6, "y": .5, "width": .2,
             "pivot": [.2, .1], "keyframes": [
                 {"t": 0, "rotation_deg": -35},
                 {"t": .4, "rotation_deg": 70, "easing": "back_out"},
             ]},
        ],
    }))
    payload = build_blender_scene(job, plan.scenes[0], 720, 1280, 24)
    assert payload["version"] == 2
    assert len(payload["parts"]) == 2
    assert payload["parts"][1]["parent"] == "torso"
    assert payload["parts"][1]["asset"] == str(arm)
    assert payload["parts"][1]["pivot"] == (0.2, 0.1)
    assert payload["parts"][1]["keyframes"][1]["easing"] == "back_out"


def test_hierarchy_rejects_cycles_unknown_parents_and_legacy_layers():
    with pytest.raises(ValidationError, match="Unknown parent"):
        PuppetRig.model_validate({"version": 2, "parts": [
            {"id": "arm", "asset": "arm.png", "parent": "missing"}]})
    with pytest.raises(ValidationError, match="cycle"):
        PuppetRig.model_validate({"version": 2, "parts": [
            {"id": "arm", "asset": "arm.png", "parent": "torso"},
            {"id": "torso", "asset": "torso.png", "parent": "arm"}]})
    with pytest.raises(ValidationError):
        PuppetRig.model_validate({"layers": [{"id": "old", "asset": "old.png"}]})


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
    try:
        link.symlink_to(outside)
    except OSError as exc:
        if getattr(exc, "winerror", None) == 1314:
            pytest.skip("Creating symlinks requires Developer Mode or elevated privileges on Windows")
        raise
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
        PuppetRig.model_validate({"version": 2, "parts": [{
            "id": "arm", "asset": "arm.png",
            "keyframes": [{"t": 0.7, "rotation_deg": 20},
                          {"t": 0.2, "rotation_deg": 30}],
        }]})
    with pytest.raises(ValidationError, match="unique"):
        PuppetRig.model_validate({"version": 2, "parts": [
            {"id": "arm", "asset": "a.png"}, {"id": "arm", "asset": "b.png"},
        ]})
    with pytest.raises(ValidationError):
        PuppetRig.model_validate({"version": 2, "parts": [
            {"id": "arm", "asset": "arm.png",
             "keyframes": [{"t": 0.2, "rotation_deg": 30, "easing": "invalid"}]},
        ]})


def test_missing_blender_explains_install(tmp_path, monkeypatch):
    job, plan = make_job(tmp_path)
    def missing_blender():
        raise FileNotFoundError("blender not found")

    monkeypatch.setattr(blender_2d, "blender_path", missing_blender)
    with pytest.raises(RuntimeError, match="Blender is required"):
        Blender2DRenderer().render(plan, str(job))


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"),
                    reason="FFmpeg and FFprobe needed for integration test")
def test_blender_mode_preserves_scene_frames_and_existing_output_contract(tmp_path, monkeypatch):
    job, plan = make_job(tmp_path, count=2)
    real_run = subprocess.run
    fake_blender_path = Path("/fake/blender")
    monkeypatch.setattr(blender_2d, "blender_path", lambda: fake_blender_path)

    def fake_blender(cmd, **kwargs):
        if Path(cmd[0]) == fake_blender_path:
            payload = json.loads(Path(cmd[-2]).read_text(encoding="utf-8"))
            frame_dir = Path(cmd[-1])
            frame_dir.mkdir(parents=True, exist_ok=True)
            for frame in range(1, payload["frames"] + 1):
                Image.new("RGB", (payload["width"], payload["height"]), "blue").save(
                    frame_dir / f"frame_{frame:04d}.png")
            return subprocess.CompletedProcess(cmd, 0)
        return real_run(cmd, **kwargs)

    monkeypatch.setattr(blender_2d.subprocess, "run", fake_blender)
    renderer = Blender2DRenderer(width=72, height=128, fps=24)
    output = renderer.render(plan, str(job), motion="static")
    assert Path(output) == job / "short.mp4"
    assert blender_2d._frame_count(job / "clips" / "scene_01.mp4") == 12
    assert blender_2d._frame_count(job / "clips" / "scene_02.mp4") == 12
    assert blender_2d._frame_count(Path(output)) == 24


def test_demo_asset_generator_works_without_blender(tmp_path):
    import sys
    demo = Path(__file__).resolve().parents[1] / "scripts" / "blender_2d_demo.py"
    job = tmp_path / "demo"
    subprocess.run([sys.executable, str(demo), "--assets-only", "--output-dir", str(job)],
                   check=True, timeout=30)
    assert (job / "background.jpg").is_file()
    from historyforgeai.application.services.puppet_templates import PUPPET_PARTS
    spec = PuppetRig.model_validate_json((job / "animation" / "scene_01.json").read_text())
    assert len(spec.parts) == len(PUPPET_PARTS) == 12
    assert next(part for part in spec.parts if part.id == "forearm_r").parent == "upper_arm_r"
    for part in spec.parts:
        assert resolve_cutout_asset(job, part.asset).is_file()
