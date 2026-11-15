"""Coordinate-based puppet assembly inspired by supplied make_art.py/build.py.

Every part is placed on one shared character canvas, then tightly cropped.
The manifest preserves original bounding boxes, pixel pivots and parenting.
The resulting v2 rig uses exact normalized coordinates and sprite widths.
"""
import json
from pathlib import Path

from PIL import Image

from historyforgeai.application.services.puppet_templates import PUPPET_PARTS
from historyforgeai.infrastructure.assets.puppet_generator import generate_puppet

CANVAS = (700, 1300)
# name: parent, joint x/y in shared canvas, displayed part size, anchor fraction,
# draw order. The source drawings are resized to this *common* character pose.
LAYOUT = {
    "torso": (None, (350, 575), (220, 280), (.5, .45), 4),
    "head": ("torso", (350, 438), (190, 220), (.5, .91), 9),
    "upper_arm_l": ("torso", (247, 485), (82, 170), (.5, .10), 3),
    "forearm_l": ("upper_arm_l", (247, 630), (75, 170), (.5, .10), 3),
    "upper_arm_r": ("torso", (453, 485), (82, 170), (.5, .10), 7),
    "forearm_r": ("upper_arm_r", (453, 630), (75, 170), (.5, .10), 8),
    "pelvis": ("torso", (350, 710), (195, 150), (.5, .10), 5),
    "thigh_l": ("pelvis", (301, 820), (92, 180), (.5, .10), 3),
    "shin_l": ("thigh_l", (301, 974), (86, 180), (.5, .10), 3),
    "thigh_r": ("pelvis", (399, 820), (92, 180), (.5, .10), 6),
    "shin_r": ("thigh_r", (399, 974), (86, 180), (.5, .10), 6),
    "weapon": ("forearm_r", (453, 768), (75, 315), (.5, .89), 10),
}


def generate_coordinate_puppet(style: str, output_dir: Path) -> dict:
    """Return a ready-to-animate v2 rig, saving cropped PNGs and a manifest."""
    output_dir = Path(output_dir)
    source = generate_puppet(style, output_dir / "source_art")
    output_dir.mkdir(parents=True, exist_ok=True)
    parts = []
    manifest = {"version": 1, "canvas": list(CANVAS), "style": style, "parts": {}}
    for name in PUPPET_PARTS:
        parent, (jx, jy), (w, h), (ax, ay), z = LAYOUT[name]
        with Image.open(source / f"{name}.png") as original:
            image = original.convert("RGBA")
            bbox = image.getchannel("A").getbbox()
            if bbox is None:
                raise ValueError(f"Empty puppet artwork: {name}")
            image = image.crop(bbox).resize((w, h), Image.Resampling.LANCZOS)
        # The anchor lies *inside* the source artwork and maps to the actual
        # shoulder/elbow/neck position on the common coordinate canvas.
        x0 = round(jx - ax * w)
        y0 = round(jy - ay * h)
        full = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
        full.alpha_composite(image, (x0, y0))
        crop = full.getchannel("A").getbbox()
        if crop is None:
            raise ValueError(f"Part outside shared canvas: {name}")
        full.crop(crop).save(output_dir / f"{name}.png")
        px = (jx - crop[0]) / (crop[2] - crop[0])
        # Blender sprite pivots use bottom-up Y; Pillow bounding boxes use top-down Y.
        py = 1.0 - (jy - crop[1]) / (crop[3] - crop[1])
        if not (0 <= px <= 1 and 0 <= py <= 1):
            raise ValueError(f"Joint outside cropped part: {name}")
        part = {
            "id": name, "asset": f"animation/assets/scene_01/{name}.png",
            "parent": parent, "x": jx / CANVAS[0], "y": jy / CANVAS[1],
            "width": (crop[2] - crop[0]) / CANVAS[0],
            "pivot": [px, py], "z": z, "keyframes": [],
        }
        parts.append(part)
        manifest["parts"][name] = {
            "bbox": list(crop), "joint": [jx, jy], "pivot": [px, py],
            "parent": parent, "z": z,
        }
    rig = {"version": 2, "parts": parts}
    (output_dir / "rig_template.json").write_text(json.dumps(rig, indent=2), encoding="utf-8")
    (output_dir / "parts.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return rig
