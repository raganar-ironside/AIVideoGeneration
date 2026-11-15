"""Regression: demo must consume coordinate-based assets, not legacy puppet_template."""
import json
from pathlib import Path

from PIL import Image

from historyforgeai.infrastructure.rendering.blender_2d import PuppetRig


def test_demo_uses_coordinate_rig(tmp_path):
    from scripts.puppet_motion_demo import prepare_scene

    job = tmp_path / "puppet"
    prepare_scene(job, "kathputli", "string-puppet")
    spec = json.loads((job / "animation" / "scene_01.json").read_text())
    rig = PuppetRig.model_validate(spec)
    manifest = json.loads((job / "generated_art" / "kathputli" / "parts.json").read_text())
    assert len(rig.parts) == len(manifest["parts"]) == 12
    assert "head" in manifest["parts"]
    for part in rig.parts:
        assert part.x == manifest["parts"][part.id]["joint"][0] / 700
        assert part.y == manifest["parts"][part.id]["joint"][1] / 1300
        assert (job / part.asset).is_file()
        with Image.open(job / part.asset) as image:
            assert image.width < 700
    assert rig.parts[0].keyframes  # Motion is applied to the calibrated rig.
