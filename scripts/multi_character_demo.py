"""Two-character shared-timeline smoke demo using simple placeholder art.

Usage:
    python scripts/multi_character_demo.py --assets-only
    python scripts/multi_character_demo.py --duration 2

Creates no hosted API calls. Both characters share one background and clock.
"""
import argparse
from pathlib import Path

from historyforgeai.application.services.puppet_scene_builder import (
    add_motion_action, approve_multi_scene, stage_character,
)
from historyforgeai.domain.models import Scene, ShortPlan
from historyforgeai.infrastructure.rendering.blender_2d import Blender2DRenderer
from blender_2d_demo import create_demo_assets


def create_multi_demo(job: Path, duration: float):
    create_demo_assets(job)
    plan = ShortPlan(
        topic="Two warrior animation demo", title="Two puppet actors",
        narration="A warrior approaches while another raises his guard",
        scenes=[Scene(
            index=1, duration_seconds=duration,
            narration="A warrior approaches while another raises his guard",
            visual_description="Two illustrated warriors in a fort",
            asset_query="fort", image_path=str(job / "background.jpg"),
        )],
    )
    (job / "scene_plan.json").write_text(plan.model_dump_json(indent=2))
    art = job / "animation" / "assets" / "scene_01"
    stage_character(job, 1, "shivaji", art, x=.28, y=.54, scale=.62)
    stage_character(job, 1, "afzal", art, x=.72, y=.54, scale=.7, depth=1)
    add_motion_action(job, 1, character="shivaji", motion="walk",
                      start=0, duration=duration * .35, distance=.12)
    add_motion_action(job, 1, character="shivaji", motion="sword_slash",
                      start=duration * .4, duration=duration * .5)
    add_motion_action(job, 1, character="afzal", motion="defend",
                      start=duration * .2, duration=duration * .65)
    approve_multi_scene(job, 1)
    return plan


def main():
    parser = argparse.ArgumentParser(description="Two-character puppet demo")
    parser.add_argument("--output-dir", type=Path, default=Path("workspace/multi_character_demo"))
    parser.add_argument("--duration", type=float, default=6)
    parser.add_argument("--assets-only", action="store_true")
    args = parser.parse_args()
    if not .25 <= args.duration <= 30:
        parser.error("Duration must be between 0.25 and 30 seconds")
    job = args.output_dir.resolve()
    job.mkdir(parents=True, exist_ok=True)
    plan = create_multi_demo(job, args.duration)
    print("Approved multi-character spec:", job / "animation" / "scene_01.json")
    if not args.assets_only:
        print("Rendered:", Blender2DRenderer(width=360, height=640, fps=24).render(
            plan, str(job), motion="static",
        ))


if __name__ == "__main__":
    main()
