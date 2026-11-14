"""Generate a twelve-part parented puppet demo to smoke-test Blender mode.

This is intentionally simple demo art, NOT a historical reconstruction.
Usage: python scripts/blender_2d_demo.py [--assets-only]
"""
import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw

from historyforgeai.domain.models import Scene, ShortPlan
from historyforgeai.infrastructure.rendering.blender_2d import Blender2DRenderer


def create_demo_assets(job: Path) -> None:
    assets = job / "animation" / "assets" / "scene_01"
    assets.mkdir(parents=True, exist_ok=True)

    # Fortress background; an approved scene image would replace this in real jobs.
    background = Image.new("RGB", (360, 640), "#d2aa7b")
    draw = ImageDraw.Draw(background)
    draw.rectangle((0, 390, 360, 640), fill="#99764f")
    draw.polygon([(0, 395), (45, 250), (125, 280), (195, 195),
                  (270, 270), (360, 240), (360, 395)], fill="#a78c6b")
    draw.rectangle((40, 285, 330, 475), fill="#9b6d4c", outline="#503f35", width=5)
    for x in range(40, 320, 38):
        draw.rectangle((x, 263, x + 24, 300), fill="#9b6d4c", outline="#503f35", width=3)
    draw.arc((105, 345, 255, 550), 180, 360, fill="#4c352d", width=14)
    draw.rectangle((115, 450, 245, 580), fill="#4c352d")
    background.save(job / "background.jpg")

    # Create twelve intentionally simple independent art pieces. Their joints
    # are connected by the v2 Blender rig, not by image-editing tricks.
    from historyforgeai.application.services.puppet_templates import (
        PUPPET_PARTS, puppet_template,
    )
    for name in PUPPET_PARTS:
        size = (120, 340) if name == "weapon" else (180, 220)
        img = Image.new("RGBA", size, (0, 0, 0, 0))
        painter = ImageDraw.Draw(img)
        if name == "torso":
            painter.polygon([(36, 50), (145, 50), (170, 188), (18, 188)],
                            fill="#a23c32", outline="#4b2c2a")
            painter.polygon([(40, 60), (90, 120), (140, 60)], fill="#d5a356")
        elif name == "head":
            painter.ellipse((40, 20, 140, 170), fill="#ba7950", outline="#603d2e", width=5)
            painter.polygon([(26, 58), (90, 0), (154, 58)], fill="#c99a45")
            painter.line([(65, 113), (115, 113)], fill="#55352c", width=4)
        elif name == "pelvis":
            painter.polygon([(24, 20), (156, 20), (140, 155), (42, 155)],
                            fill="#a23c32", outline="#4b2c2a")
        elif name.startswith(("upper_arm", "forearm")):
            painter.line([(88, 22), (95, 195)], fill="#bd875c", width=46)
            painter.ellipse((65, 5, 110, 50), fill="#bd875c")
        elif name.startswith(("thigh", "shin")):
            painter.line([(90, 15), (90, 200)], fill="#62412d", width=54)
        elif name == "weapon":
            painter.line([(34, 305), (84, 30)], fill="#c4c8d0", width=14)
            painter.polygon([(84, 30), (102, 3), (91, 53)], fill="#e0e3e8")
            painter.line([(8, 270), (73, 284)], fill="#644a2b", width=13)
        img.save(assets / f"{name}.png")

    animation = job / "animation" / "scene_01.json"
    animation.write_text(json.dumps(puppet_template(1), indent=2), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Create a Blender 2D cutout demo")
    parser.add_argument("--output-dir", type=Path, default=Path("workspace/blender_demo"))
    parser.add_argument("--assets-only", action="store_true", help="Generate PNGs/JSON without Blender")
    parser.add_argument("--duration", type=float, default=6.0)
    args = parser.parse_args()
    if not 0 < args.duration <= 30:
        parser.error("--duration must be between 0 and 30 seconds")
    job = args.output_dir.resolve()
    create_demo_assets(job)
    print(f"Demo cutout assets: {job / 'animation'}")
    if args.assets_only:
        return
    plan = ShortPlan(
        topic="Illustrated fortress demo", title="Chandragupta cutout prototype",
        narration="A historical illustration demo",
        scenes=[Scene(index=1, duration_seconds=args.duration,
                      narration="A historical illustration demo",
                      visual_description="Commander raises a sword at a fort",
                      asset_query="fortress", image_path=str(job / "background.jpg"))],
    )
    renderer = Blender2DRenderer(width=360, height=640, fps=24)
    print("Rendered:", renderer.render(plan, str(job), motion="static"))


if __name__ == "__main__":
    main()
