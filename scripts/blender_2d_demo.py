"""Generate an illustrated placeholder cutout scene to smoke-test Blender mode.

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
    assets = job / "animation" / "assets"
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

    # Transparent body and head.
    body = Image.new("RGBA", (260, 450), (0, 0, 0, 0))
    d = ImageDraw.Draw(body)
    d.polygon([(95, 290), (125, 420), (140, 420), (145, 290)], fill="#62412d")
    d.polygon([(150, 290), (160, 420), (180, 420), (175, 290)], fill="#62412d")
    d.polygon([(80, 135), (190, 135), (215, 320), (60, 320)], fill="#a23c32", outline="#4b2c2a")
    d.polygon([(75, 137), (130, 185), (190, 137)], fill="#d5a356")
    d.ellipse((102, 45, 171, 135), fill="#ba7950", outline="#603d2e", width=4)
    d.polygon([(88, 65), (130, 18), (188, 65), (175, 85), (92, 85)], fill="#c99a45", outline="#63422c")
    d.line([(115, 102), (155, 102)], fill="#55352c", width=4)
    body.save(assets / "chandragupta_body.png")

    # Separate sword arm, with its pivot near the shoulder in the top-left.
    arm = Image.new("RGBA", (190, 260), (0, 0, 0, 0))
    d = ImageDraw.Draw(arm)
    d.line([(28, 32), (65, 105), (105, 165)], fill="#b77d51", width=29)
    d.ellipse((88, 145, 120, 175), fill="#b77d51")
    d.line([(105, 160), (155, 230)], fill="#c4c8d0", width=11)
    d.polygon([(155, 230), (169, 249), (158, 220)], fill="#e0e3e8")
    d.line([(85, 175), (123, 153)], fill="#644a2b", width=9)
    arm.save(assets / "chandragupta_sword_arm.png")

    animation = job / "animation" / "scene_01.json"
    animation.write_text(json.dumps({
        "layers": [
            {
                "id": "body", "asset": "animation/assets/chandragupta_body.png",
                "x": 0.5, "y": 0.65, "width": 0.55, "z": 1,
                "keyframes": [{"t": 0, "scale": 1}, {"t": 1, "scale": 1.03}],
            },
            {
                "id": "sword_arm", "asset": "animation/assets/chandragupta_sword_arm.png",
                "x": 0.59, "y": 0.53, "width": 0.24,
                "pivot": [0.15, 0.12], "z": 2,
                "keyframes": [
                    {"t": 0, "rotation_deg": -40},
                    {"t": 0.45, "rotation_deg": 65},
                    {"t": 1, "rotation_deg": 65},
                ],
            },
        ]
    }, indent=2), encoding="utf-8")


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
