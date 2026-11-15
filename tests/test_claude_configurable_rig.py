"""Fast scene-contract tests for the experimental configurable rig."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REF = ROOT / "reference" / "claude_shiva"


def test_configurable_rig_source_compiles():
    for path in (REF / "blender_configurable_rig.py",
                 ROOT / "scripts" / "claude_rig_demo.py"):
        compile(path.read_text(encoding="utf-8"), str(path), "exec")


def test_scene_joint_hierarchy_and_animation_times():
    spec = json.loads((REF / "scenes" / "shiva_five_second.json").read_text())
    pivots = spec["rig"]["pivots"]
    assert spec["rig"]["root"] == "root"
    assert spec["duration"] == 5 and spec["fps"] == 24
    for name in pivots:
        seen = set()
        current = name
        while current != "root":
            assert current not in seen, "Joint hierarchy contains a cycle"
            seen.add(current)
            current = pivots[current]["parent"]
            assert current in pivots
    valid = set(pivots) | {layer["id"] for layer in spec["overlays"]}
    for name, channels in spec["animation"].items():
        assert name in valid
        for points in channels.values():
            times = [point[0] for point in points]
            assert times == sorted(set(times))
            frames = [min(round(spec["fps"] * spec["duration"]),
                          1 + round(t * spec["fps"])) for t in times]
            assert frames == sorted(set(frames))
            assert all(0 <= t <= spec["duration"] for t in times)


def test_preview_cli_and_eevee_support_are_present():
    runner = (ROOT / "scripts" / "claude_rig_demo.py").read_text()
    renderer = (REF / "blender_configurable_rig.py").read_text()
    assert 'p.add_argument("--preview"' in runner
    assert 'p.add_argument("--frame"' in runner
    assert 'p.add_argument("--engine"' in runner
    assert '"BLENDER_EEVEE_NEXT"' in renderer
    assert '"BLENDER_EEVEE"' in renderer
    assert 'bpy.ops.render.render(write_still=True)' in renderer
    assert 'm.surface_render_method = "DITHERED"' in renderer


def test_reusable_effects_are_valid_and_water_is_not_double_animated():
    spec = json.loads((REF / "scenes" / "shiva_five_second.json").read_text())
    overlays = {layer["id"]: layer for layer in spec["overlays"]}
    assert "water" not in spec["animation"]
    assert spec["effects"]
    for effect in spec["effects"]:
        assert effect["id"] in overlays
        assert effect["easing"] in ("BEZIER", "LINEAR", "CONSTANT")
        for channel, points in effect["channels"].items():
            assert channel in ("x", "y", "rotation_deg", "opacity")
            times = [point[0] for point in points]
            assert times == sorted(set(times))
            assert all(0 <= t <= spec["duration"] for t in times)
            if channel == "opacity":
                assert all(0 <= value <= 1 for _, value in points)
    assert spec["effects"][0]["channels"]["y"][-1][1] < 0


def test_effects_renderer_supports_alpha_keyframes():
    renderer = (REF / "blender_configurable_rig.py").read_text()
    assert 'elif channel == "opacity":' in renderer
    assert 'spec.get("effects", [])' in renderer
    assert 'key.handle_left_type = "AUTO_CLAMPED"' in renderer
