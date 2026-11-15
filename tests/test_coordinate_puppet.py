import json

import pytest
from PIL import Image

from historyforgeai.infrastructure.assets.coordinate_puppet import (
    CANVAS, LAYOUT, generate_coordinate_puppet,
)
from historyforgeai.infrastructure.rendering.blender_2d import PuppetRig


@pytest.mark.parametrize("style", ["kathputli", "paper-cutout"])
def test_coordinate_rig_valid_and_joint_anchored(style, tmp_path):
    folder = tmp_path / style
    data = generate_coordinate_puppet(style, folder)
    rig = PuppetRig.model_validate(data)
    manifest = json.loads((folder / "parts.json").read_text())
    assert tuple(manifest["canvas"]) == CANVAS
    assert len(rig.parts) == 12
    for part in rig.parts:
        meta = manifest["parts"][part.id]
        x0, y0, x1, y1 = meta["bbox"]
        jx, jy = meta["joint"]
        assert abs((jx - x0) / (x1 - x0) - part.pivot[0]) < 1e-6
        assert abs(1 - (jy - y0) / (y1 - y0) - part.pivot[1]) < 1e-6
        assert (jx, jy) == LAYOUT[part.id][1]
        with Image.open(folder / f"{part.id}.png") as image:
            assert image.size == (x1 - x0, y1 - y0)
            assert image.getchannel("A").getbbox()
