"""Multi-character v3, reusable motion clips, approval and Blender payload tests."""
import json
from pathlib import Path

import pytest
from PIL import Image
from pydantic import ValidationError

from historyforgeai.application.services.motion_library import (
    MotionClip, available_motions, load_motion,
)
from historyforgeai.application.services.puppet_scene_builder import (
    add_motion_action, approve_multi_scene, load_multi_draft, preview_multi_scene,
    remove_motion_action, stage_character, update_character_joints,
)
from historyforgeai.application.services.puppet_timeline import (
    MultiCharacterScene, compile_multi_character_scene,
)
from historyforgeai.application.services.puppet_templates import PUPPET_PARTS
from historyforgeai.application.services.illustrated_assets import verify_approved_assets
from historyforgeai.domain.models import Scene, ShortPlan
from historyforgeai.infrastructure.rendering.blender_2d import build_blender_scene


@pytest.fixture
def job(tmp_path):
    path = tmp_path / "workspace" / "jobs" / "demo"
    path.mkdir(parents=True)
    bg = path / "background.jpg"
    Image.new("RGB", (90, 160), "navy").save(bg)
    plan = ShortPlan(
        topic="Historical scene", title="Two warriors", narration="Confrontation",
        scenes=[Scene(index=1, duration_seconds=6, narration="Confrontation",
                      visual_description="Two warriors", asset_query="fort",
                      image_path=str(bg))],
    )
    (path / "scene_plan.json").write_text(plan.model_dump_json(indent=2))
    return path, plan


def puppet_art(tmp_path, name):
    root = tmp_path / name
    root.mkdir()
    for part in PUPPET_PARTS:
        Image.new("RGBA", (40, 50), (120, 70, 30, 255)).save(root / f"{part}.png")
    return root


def stage_two(job, tmp_path):
    path, _ = job
    stage_character(path, 1, "shivaji", puppet_art(tmp_path, "shivaji"), x=.3, scale=.65)
    stage_character(path, 1, "afzal", puppet_art(tmp_path, "afzal"), x=.7, scale=.8, depth=1)
    return path


def test_two_characters_share_clock_and_render_independently(job, tmp_path):
    path = stage_two(job, tmp_path)
    add_motion_action(path, 1, character="shivaji", motion="walk",
                      start=0, duration=2, repeat=2, distance=.2)
    add_motion_action(path, 1, character="shivaji", motion="sword_slash",
                      start=2, duration=1)
    add_motion_action(path, 1, character="afzal", motion="defend",
                      start=2, duration=1)
    approved = approve_multi_scene(path, 1)
    assert approved.is_file()
    verify_approved_assets(path, 1)
    payload = build_blender_scene(path, job[1].scenes[0], 360, 640, 24)
    assert payload["version"] == 2  # v3 authored spec compiles to trusted Blender v2.
    assert len(payload["parts"]) == 24
    ids = {p["id"] for p in payload["parts"]}
    assert "shivaji__torso" in ids and "afzal__torso" in ids
    assert next(p for p in payload["parts"] if p["id"] == "shivaji__forearm_r")["parent"] == "shivaji__upper_arm_r"
    assert next(p for p in payload["parts"] if p["id"] == "afzal__forearm_r")["parent"] == "afzal__upper_arm_r"
    shivaji = next(p for p in payload["parts"] if p["id"] == "shivaji__torso")
    afzal = next(p for p in payload["parts"] if p["id"] == "afzal__torso")
    assert shivaji["x"] != afzal["x"]
    assert shivaji["z"] < afzal["z"]
    assert shivaji["asset"].endswith("/shivaji/torso.png")
    # Root motion accumulates through walking and is retained during sword slash.
    slash_start = next(k for k in shivaji["keyframes"] if abs(k["t"] - 2/6) < 1e-7)
    assert slash_start["dx"] == pytest.approx(.2)
    assert next(p for p in payload["parts"] if p["id"] == "afzal__upper_arm_r")["keyframes"]


def test_three_characters_exceed_old_32_part_limit(job, tmp_path):
    path, plan = job
    for i in range(3):
        stage_character(path, 1, f"warrior{i}", puppet_art(tmp_path, f"warrior{i}"))
    approve_multi_scene(path, 1)
    payload = build_blender_scene(path, plan.scenes[0], 360, 640, 24)
    assert len(payload["parts"]) == 36


def test_overlapping_same_actor_rejected_but_other_actor_allowed(job, tmp_path):
    path = stage_two(job, tmp_path)
    add_motion_action(path, 1, character="shivaji", motion="point", start=0, duration=2)
    with pytest.raises(ValidationError, match="Overlapping"):
        add_motion_action(path, 1, character="shivaji", motion="bow", start=1, duration=2)
    add_motion_action(path, 1, character="afzal", motion="bow", start=1, duration=2)
    assert len(load_multi_draft(path, 1)["timeline"]) == 2


def test_unknown_joint_and_scene_overrun_rejected_before_approval(job, tmp_path):
    path, _ = job
    stage_character(path, 1, "hero", puppet_art(tmp_path, "hero"))
    with pytest.raises(ValueError, match="after scene duration"):
        add_motion_action(path, 1, character="hero", motion="run", start=5, duration=2)
    with pytest.raises(ValueError, match="Unknown motion"):
        add_motion_action(path, 1, character="hero", motion="teleport", start=0, duration=1)
    assert not load_multi_draft(path, 1)["timeline"]


def test_custom_motion_and_hash_pinning(job, tmp_path):
    path, _ = job
    stage_character(path, 1, "hero", puppet_art(tmp_path, "hero"))
    library = path.parent.parent / "motions"
    library.mkdir()
    custom = library / "salute.json"
    custom.write_text(json.dumps({
        "name": "salute", "description": "Custom salute",
        "tracks": {"upper_arm_r": [
            {"t": 0, "rotation_deg": 0},
            {"t": .5, "rotation_deg": 55, "easing": "back_out"},
            {"t": 1, "rotation_deg": 0},
        ]},
    }))
    assert "salute" in available_motions(path)
    assert load_motion(path, "salute").name == "salute"
    add_motion_action(path, 1, character="hero", motion="salute", start=1, duration=2)
    approve_multi_scene(path, 1)
    verify_approved_assets(path, 1)
    custom.write_text(custom.read_text() + "\n")
    with pytest.raises(ValueError, match="changed after approval"):
        verify_approved_assets(path, 1)


def test_custom_motion_validates_endpoints_and_unknown_joint(job, tmp_path):
    path, _ = job
    stage_character(path, 1, "hero", puppet_art(tmp_path, "hero"))
    with pytest.raises(ValidationError, match="neutral"):
        MotionClip.model_validate({
            "name": "invalid", "tracks": {"head": [
                {"t": 0, "rotation_deg": 10}, {"t": 1, "rotation_deg": 0},
            ]}
        })
    custom = path / "motions"
    custom.mkdir()
    (custom / "tail_wag.json").write_text(json.dumps({
        "name": "tail_wag", "tracks": {"tail": [
            {"t": 0, "rotation_deg": 0}, {"t": 1, "rotation_deg": 0},
        ]}
    }))
    with pytest.raises(ValueError, match="missing joints"):
        add_motion_action(path, 1, character="hero", motion="tail_wag", start=0, duration=1)


def test_asset_tamper_fails_closed_and_draft_does_not_replace_live(job, tmp_path):
    path, _ = job
    stage_character(path, 1, "hero", puppet_art(tmp_path, "hero"))
    approve_multi_scene(path, 1)
    live = path / "animation" / "scene_01.json"
    before = live.read_bytes()
    # New action is staged, but not yet visible to Blender.
    add_motion_action(path, 1, character="hero", motion="point", start=0, duration=1)
    assert live.read_bytes() == before
    verify_approved_assets(path, 1)
    approve_multi_scene(path, 1)
    assert live.read_bytes() != before
    asset = path / "animation" / "assets" / "scene_01" / "characters" / "hero" / "head.png"
    Image.new("RGBA", (40, 50), (20, 100, 50, 255)).save(asset)
    with pytest.raises(ValueError, match="changed after approval"):
        verify_approved_assets(path, 1)


def test_incomplete_or_opaque_parts_cannot_stage(job, tmp_path):
    path, _ = job
    source = puppet_art(tmp_path, "bad")
    (source / "head.png").unlink()
    with pytest.raises(ValueError, match="Missing or oversized"):
        stage_character(path, 1, "bad", source)
    assert load_multi_draft(path, 1) is None
    Image.new("RGB", (30, 30), "white").save(source / "head.png")
    with pytest.raises(ValueError, match="transparency"):
        stage_character(path, 1, "bad", source)
    assert load_multi_draft(path, 1) is None


def test_edit_joints_preview_and_remove_action(job, tmp_path):
    path, _ = job
    stage_character(path, 1, "hero", puppet_art(tmp_path, "hero"))
    draft = load_multi_draft(path, 1)
    rows = [
        {"id": p["id"], "parent": p.get("parent") or "", "x": p["x"], "y": p["y"],
         "width": p["width"], "pivot_x": p["pivot"][0],
         "pivot_y": p["pivot"][1], "z": p["z"]}
        for p in draft["characters"][0]["parts"]
    ]
    rows[0]["x"] = .55
    update_character_joints(path, 1, "hero", rows)
    assert load_multi_draft(path, 1)["characters"][0]["parts"][0]["x"] == .55
    preview = preview_multi_scene(path, 1)
    assert preview.is_file()
    add_motion_action(path, 1, character="hero", motion="idle", start=0, duration=1)
    remove_motion_action(path, 1, 0)
    assert load_multi_draft(path, 1)["timeline"] == []


def test_repeat_root_displacement_persists_across_actions(job, tmp_path):
    path, _ = job
    stage_character(path, 1, "hero", puppet_art(tmp_path, "hero"))
    add_motion_action(path, 1, character="hero", motion="walk",
                      start=0, duration=2, repeat=4, distance=.4, direction=-1)
    add_motion_action(path, 1, character="hero", motion="bow", start=2, duration=1)
    spec = MultiCharacterScene.model_validate(load_multi_draft(path, 1))
    parts = compile_multi_character_scene(spec, path, 6)
    torso = next(p for p in parts if p["id"] == "hero__torso")
    at_two = next(k for k in torso["keyframes"] if abs(k["t"] - 2/6) < 1e-7)
    assert at_two["dx"] == pytest.approx(-.4)
    assert any(k["rotation_deg"] != 0 for k in torso["keyframes"] if "rotation_deg" in k)


def test_invalid_v3_parent_and_character_reference():
    with pytest.raises(ValidationError):
        MultiCharacterScene.model_validate({"version": 3, "characters": [
            {"id": "hero", "parts": [{"id": "head", "asset": "head.png",
                                      "parent": "missing"}]}
        ]})
    with pytest.raises(ValidationError, match="Unknown timeline character"):
        MultiCharacterScene.model_validate({"version": 3, "characters": [
            {"id": "hero", "parts": [{"id": "head", "asset": "head.png"}]}
        ], "timeline": [{"character": "other", "motion": "idle",
                         "start": 0, "duration": 1}]})


def test_v3_scene_without_approval_is_rejected(job, tmp_path):
    path, plan = job
    stage_character(path, 1, "hero", puppet_art(tmp_path, "hero"))
    draft = load_multi_draft(path, 1)
    live = path / "animation" / "scene_01.json"
    live.parent.mkdir(parents=True, exist_ok=True)
    live.write_text(json.dumps(draft))
    with pytest.raises(ValueError, match="explicitly approved"):
        verify_approved_assets(path, 1)


def test_real_demo_generates_two_approved_characters_without_blender(tmp_path):
    import subprocess
    import sys
    demo = Path(__file__).resolve().parents[1] / "scripts" / "multi_character_demo.py"
    output = tmp_path / "demo"
    subprocess.run([sys.executable, str(demo), "--assets-only",
                    "--output-dir", str(output), "--duration", "2"],
                   check=True, timeout=40)
    spec = MultiCharacterScene.model_validate_json(
        (output / "animation" / "scene_01.json").read_text()
    )
    assert len(spec.characters) == 2
    assert len(spec.timeline) == 3
    verify_approved_assets(output, 1)


def test_root_motion_interpolates_when_torso_has_intermediate_keyframes(job, tmp_path):
    path, _ = job
    stage_character(path, 1, "hero", puppet_art(tmp_path, "hero"))
    custom = path / "motions"
    custom.mkdir()
    (custom / "advance.json").write_text(json.dumps({
        "name": "advance",
        "tracks": {
            "root": [{"t": 0, "dx": 0}, {"t": 1, "dx": 1}],
            "torso": [
                {"t": 0, "rotation_deg": 0},
                {"t": .5, "rotation_deg": 20},
                {"t": 1, "rotation_deg": 0},
            ],
        },
    }))
    add_motion_action(path, 1, character="hero", motion="advance",
                      start=0, duration=2, distance=.4)
    spec = MultiCharacterScene.model_validate(load_multi_draft(path, 1))
    torso = next(p for p in compile_multi_character_scene(spec, path, 6)
                 if p["id"] == "hero__torso")
    middle = next(k for k in torso["keyframes"] if abs(k["t"] - 1/6) < 1e-7)
    assert middle["dx"] == pytest.approx(.2)
    assert middle["rotation_deg"] == pytest.approx(20)
