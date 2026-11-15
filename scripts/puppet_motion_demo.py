"""Render a five-second Maratha puppet animation in two movement styles.

Uses procedural Phase 1 PNG parts and the existing Blender2DRenderer.
"""
import argparse
import json
from pathlib import Path

from historyforgeai.domain.models import Scene, ShortPlan
from historyforgeai.infrastructure.assets.coordinate_puppet import generate_coordinate_puppet
from historyforgeai.infrastructure.rendering.blender_2d import Blender2DRenderer
from blender_2d_demo import create_demo_assets


def motion_rig(mode: str, rig: dict | None = None) -> dict:
    if mode not in ("string-puppet", "hinged-cutout"):
        raise ValueError(f"Unknown mode: {mode}")
    if rig is None:
        from historyforgeai.application.services.puppet_templates import puppet_template
        rig = puppet_template(1)
    parts = {part["id"]: part for part in rig["parts"]}
    def keys(name, values):
        parts[name]["keyframes"] = values
    def k(t, **kwargs):
        return {"t": t, "easing": "ease_in_out", **kwargs}
    # Normalized timeline: entrance, face audience, sword lift, moustache,
    # final heroic pose. All transforms are relative to the bind pose.
    bounce = 0.018 if mode == "string-puppet" else 0.004
    keys("torso", [
        k(0.00, dx=-0.65, dy=0.0, rotation_deg=-7),
        k(0.20, dx=0, dy=-bounce, rotation_deg=5 if bounce > .01 else 0),
        k(0.40, dx=0, dy=0, rotation_deg=-4 if bounce > .01 else 0),
        k(0.80, dx=0, dy=-bounce, rotation_deg=2),
        k(1.00, dx=0, dy=0, rotation_deg=0),
    ])
    keys("head", [
        k(0, rotation_deg=-10), k(.25, rotation_deg=-10),
        k(.40, rotation_deg=8), k(.60, rotation_deg=0),
        k(1, rotation_deg=0),
    ])
    keys("upper_arm_r", [
        k(0, rotation_deg=-12), k(.40, rotation_deg=0),
        k(.60, rotation_deg=85), k(1, rotation_deg=85),
    ])
    keys("forearm_r", [
        k(0, rotation_deg=5), k(.40, rotation_deg=0),
        k(.60, rotation_deg=-30), k(1, rotation_deg=-30),
    ])
    keys("upper_arm_l", [
        k(0, rotation_deg=-12), k(.60, rotation_deg=0),
        k(.77, rotation_deg=-55), k(.88, rotation_deg=-65),
        k(1, rotation_deg=-20),
    ])
    keys("forearm_l", [
        k(0, rotation_deg=10), k(.60, rotation_deg=0),
        k(.77, rotation_deg=-65), k(.88, rotation_deg=-75),
        k(1, rotation_deg=-15),
    ])
    if mode == "string-puppet":
        for name, angle in (("thigh_l", 13), ("thigh_r", -13),
                            ("shin_l", -9), ("shin_r", 9)):
            keys(name, [k(0, rotation_deg=angle),
                        k(.12, rotation_deg=-angle),
                        k(.25, rotation_deg=angle),
                        k(.40, rotation_deg=0), k(1, rotation_deg=0)])
    else:
        for name in ("thigh_l", "thigh_r", "shin_l", "shin_r"):
            keys(name, [k(0, rotation_deg=0), k(1, rotation_deg=0)])
    # Weapon is parented to the right forearm, so follows sword arm.
    keys("weapon", [k(0, rotation_deg=0), k(1, rotation_deg=0)])
    return rig


def prepare_scene(job: Path, style: str, mode: str) -> None:
    create_demo_assets(job)  # provides the existing painted fort backdrop
    rig = generate_coordinate_puppet(style, job / "generated_art" / style)
    target = job / "animation" / "assets" / "scene_01"
    import shutil
    for png in source.glob("*.png"):
        shutil.copy2(png, target / png.name)
    rig = motion_rig(mode, rig)
    (job / "animation" / "scene_01.json").write_text(
        json.dumps(rig, indent=2), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Animate a procedural Maratha puppet")
    parser.add_argument("--mode", choices=("string-puppet", "hinged-cutout", "both"), default="both")
    parser.add_argument("--assets-only", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=Path("workspace/puppet_motion"))
    args = parser.parse_args()
    modes = ("string-puppet", "hinged-cutout") if args.mode == "both" else (args.mode,)
    for mode in modes:
        style = "kathputli" if mode == "string-puppet" else "paper-cutout"
        job = (args.output_dir / mode).resolve()
        prepare_scene(job, style, mode)
        if args.assets_only:
            print("Prepared:", job)
            continue
        plan = ShortPlan(
            topic="Maratha puppet prototype", title="Maratha puppet motion test",
            narration="A stylized puppet demonstration",
            scenes=[Scene(index=1, duration_seconds=5,
                          narration="A stylized puppet demonstration",
                          visual_description="Warrior enters, raises sword and gestures",
                          asset_query="fort", image_path=str(job / "background.jpg"))],
        )
        renderer = Blender2DRenderer(width=360, height=640, fps=24)
        print("Rendered:", renderer.render(plan, str(job), motion="static"))


if __name__ == "__main__":
    main()
