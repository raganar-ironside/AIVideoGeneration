"""Generate reusable Maratha warrior puppet PNG layers using Pillow only.

The artwork is intentionally stylized Indian folk theatre, not photorealism.
Both styles export the same 12 part names consumed by the Blender puppet rig.
"""
import json
from pathlib import Path

from PIL import Image, ImageDraw

from historyforgeai.application.services.puppet_templates import PUPPET_PARTS, puppet_template

SIZE = (240, 300)
STYLES = ("kathputli", "paper-cutout")


def _layer(name: str, style: str) -> Image.Image:
    im = Image.new("RGBA", SIZE)
    d = ImageDraw.Draw(im)
    ink = "#38251f"
    skin = "#c98250"
    saffron = "#e68c2f"
    coat = "#a73d37" if style == "kathputli" else "#bf5634"
    trim = "#e9bd67"
    joint = "#64402e"
    if name == "head":
        d.ellipse((48, 58, 192, 240), fill=skin, outline=ink, width=6)
        d.polygon([(36, 92), (72, 34), (170, 27), (210, 90)], fill=saffron, outline=ink)
        for y in (60, 75):
            d.arc((50, y, 195, y+34), 185, 355, fill=trim, width=5)
        d.ellipse((77, 126, 92, 140), fill=ink)
        d.ellipse((149, 126, 164, 140), fill=ink)
        d.arc((78, 146, 162, 206), 10, 170, fill=ink, width=10)
        d.arc((52, 151, 126, 211), 190, 340, fill=ink, width=9)
        d.arc((116, 151, 193, 211), 200, 350, fill=ink, width=9)
        d.arc((98, 196, 146, 223), 0, 170, fill="#7d3b32", width=4)
    elif name == "torso":
        d.polygon([(53, 25), (186, 25), (212, 247), (29, 247)], fill=coat, outline=ink)
        d.polygon([(65, 31), (121, 119), (174, 31), (157, 31), (120, 82), (85, 31)],
                  fill=trim)
        d.line([(46, 206), (194, 206)], fill=trim, width=15)
        d.line([(47, 229), (193, 229)], fill=ink, width=4)
        if style == "kathputli":
            for x in (73, 116, 159):
                d.ellipse((x, 164, x+9, 173), fill=trim)
    elif name == "pelvis":
        d.polygon([(48, 18), (191, 18), (210, 224), (30, 224)], fill="#d8ad6d", outline=ink)
        d.polygon([(115, 30), (144, 217), (97, 217)], fill="#ad6546")
        for x in (60, 180):
            d.line([(x, 70), (120, 232)], fill=trim, width=4)
    elif name.startswith(("upper_arm", "forearm")):
        upper = name.startswith("upper")
        d.rounded_rectangle((78, 22, 159, 239), radius=34,
                            fill=coat if upper else skin, outline=ink, width=6)
        d.ellipse((92, 29, 144, 80), fill=trim if upper else skin, outline=ink, width=4)
        if not upper:
            d.rounded_rectangle((76, 197, 162, 265), radius=24, fill=skin, outline=ink, width=5)
        if style == "paper-cutout":
            d.ellipse((109, 37, 132, 60), fill=trim, outline=ink, width=3)
    elif name.startswith(("thigh", "shin")):
        d.rounded_rectangle((75, 15, 164, 251), radius=22,
                            fill="#f0c37c" if name.startswith("thigh") else "#654a3a",
                            outline=ink, width=6)
        d.line([(99, 36), (99, 230)], fill=trim, width=5)
        if name.startswith("shin"):
            d.ellipse((65, 221, 184, 273), fill="#4d332a", outline=ink, width=5)
    elif name == "weapon":
        d.polygon([(116, 30), (133, 6), (142, 39), (128, 225), (116, 225)],
                  fill="#cbd7db", outline=ink)
        d.line([(78, 226), (165, 226)], fill=trim, width=14)
        d.line([(125, 223), (125, 280)], fill="#69442b", width=16)
        d.ellipse((113, 268, 137, 292), fill=trim, outline=ink, width=3)
    else:
        raise ValueError(f"Unknown puppet part: {name}")
    return im


def generate_puppet(style: str, output_dir: Path) -> Path:
    if style not in STYLES:
        raise ValueError(f"Style must be one of {STYLES}")
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    for name in PUPPET_PARTS:
        _layer(name, style).save(output_dir / f"{name}.png")
    # This template uses approximate pivots: review alignment before rendering.
    (output_dir / "rig_template.json").write_text(
        json.dumps(puppet_template(1), indent=2), encoding="utf-8")
    (output_dir / "manifest.json").write_text(json.dumps({
        "style": style, "character": "maratha_warrior",
        "parts": list(PUPPET_PARTS), "status": "needs_joint_review",
        "notes": "Procedural artwork; refine placement and pivots for production.",
    }, indent=2), encoding="utf-8")
    return output_dir
