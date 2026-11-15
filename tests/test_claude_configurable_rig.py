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
