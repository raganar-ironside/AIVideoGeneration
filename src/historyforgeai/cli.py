import argparse
import os
import csv
import json
import sys
from historyforgeai.bootstrap import build
from historyforgeai.config import ROOT, settings
from historyforgeai.domain.characters import Character
from historyforgeai.infrastructure.persistence.characters import CharacterRegistry
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(prog="historyforgeai", description="HistoryForgeAI Shorts pipeline")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="Plan and optionally render a Short")
    run.add_argument("--topic", required=True)
    run.add_argument("--provider", choices=["mock","gemini","ollama","groq","openrouter","openai"], default=None)
    run.add_argument("--model", help="Model override for Groq, OpenRouter, or OpenAI")
    run.add_argument("--allow-paid", action="store_true", help="Explicitly allow paid API calls")
    run.add_argument("--assets", action="store_true", help="Download Wikimedia images (requires network)")
    run.add_argument("--research", action="store_true", help="Retrieve Wikipedia background (not fact-checking)")
    run.add_argument("--no-audio", action="store_true")
    run.add_argument("--no-render", action="store_true")
    run.add_argument("--duration", type=int)
    run.add_argument("--scenes", type=int)
    run.add_argument('--scene-audio', action='store_true', help='Narrate scenes separately and align image timing to actual speech')
    run.add_argument('--motion', choices=['static','zoom_in','zoom_out'], default='zoom_in')
    manual = sub.add_parser("import-script", help="Import manually written narration and scene breakdown")
    manual.add_argument("--file", required=True, type=Path, help="JSON file containing full narration and scenes")
    chars = sub.add_parser('characters', help='Manage canonical character references')
    charsub = chars.add_subparsers(dest='character_command', required=True)
    create = charsub.add_parser('add')
    create.add_argument('--id', required=True)
    create.add_argument('--name', required=True)
    create.add_argument('--universe', required=True)
    create.add_argument('--description', default='')
    approve = charsub.add_parser('approve')
    approve.add_argument('--id', required=True)
    approve.add_argument('--image', required=True)
    charsub.add_parser('list')
    story = sub.add_parser('storyboard', help='Create or apply a reviewable storyboard')
    story.add_argument('--job', required=True, help='Existing job ID')
    story.add_argument('--apply', action='store_true', help='Apply only if every scene is approved')
    render_cmd = sub.add_parser("render", help="Render an existing approved storyboard")
    render_cmd.add_argument("--job", required=True, help="Existing job ID")
    render_cmd.add_argument("--motion", choices=["static", "zoom_in", "zoom_out"], default="zoom_in")
    images = sub.add_parser("image", help="Add a manual or hosted candidate image for storyboard review")
    images.add_argument("--job", required=True)
    images.add_argument("--scene", required=True, type=int)
    images.add_argument("--provider", choices=["manual", "huggingface", "openai"], default="manual")
    images.add_argument("--file", type=Path, help="Existing local image for manual mode")
    images.add_argument("--model", help="Hosted image model override")
    images.add_argument("--allow-paid", action="store_true", help="Allow potentially billed hosted image calls")
    sub.add_parser("list", help="List jobs")
    sub.add_parser("topics", help="Show queued topics")
    args = parser.parse_args()
    config = settings()
    if args.command == "run":
        try:
            provider = args.provider or os.getenv("LLM_PROVIDER", "mock")
            model = args.model or os.getenv(f"{provider.upper()}_MODEL", "")
            if provider == "openai" or (provider == "openrouter" and model != "openrouter/free" and not model.endswith(":free")):
                if not args.allow_paid:
                    raise ValueError("Paid or potentially paid provider/model requires --allow-paid")
            pipeline = build(provider, model=args.model)
            job = pipeline.run(args.topic, duration=args.duration or config["duration_seconds"],
                scenes=args.scenes or config["scene_count"], fetch_assets=args.assets,
                synthesize_audio=not args.no_audio, render=not args.no_render,
                research_enabled=args.research, scene_audio=args.scene_audio, motion=args.motion)
            print(job.model_dump_json(indent=2))
        except Exception as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            sys.exit(1)
    elif args.command == "import-script":
        from historyforgeai.application.services.manual_script import import_script
        from historyforgeai.infrastructure.persistence.filesystem import FileJobRepository
        work = ROOT / "workspace"
        try:
            job = import_script(args.file, work, FileJobRepository(work / "jobs"))
            print(job.model_dump_json(indent=2))
        except Exception as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            sys.exit(1)
    elif args.command == 'characters':
        registry = CharacterRegistry(ROOT / 'workspace' / 'characters')
        if args.character_command == 'add':
            character = Character(id=args.id, display_name=args.name, universe=args.universe,
                                  description=args.description)
            print(registry.save(character))
        elif args.character_command == 'approve':
            character = registry.get(args.id)
            image = Path(args.image).expanduser().resolve()
            if not image.is_file():
                parser.error(f'Image does not exist: {image}')
            character.canonical_image = str(image)
            character.approved = True
            print(registry.save(character))
        else:
            for character in registry.list():
                print(f'{character.id} | {character.display_name} | {character.universe} | approved={character.approved}')
    elif args.command == 'storyboard':
        from historyforgeai.application.services.storyboard import make_storyboard, save, apply_approved
        folder = ROOT / 'workspace' / 'jobs' / args.job
        plan_path = folder / 'scene_plan.json'
        board_path = folder / 'storyboard.json'
        if not plan_path.is_file():
            parser.error(f'Job plan not found: {plan_path}')
        if args.apply:
            print(f'Applied {apply_approved(plan_path,board_path)} approved scenes')
        else:
            from historyforgeai.domain.models import ShortPlan
            plan = ShortPlan.model_validate_json(plan_path.read_text(encoding='utf-8'))
            if board_path.exists():
                parser.error('Storyboard already exists; not overwriting human reviews')
            board = make_storyboard(plan,CharacterRegistry(ROOT/'workspace'/'characters'))
            save(board_path,board)
            print(f'Created {board_path} with {len(board.shots)} scenes')
    elif args.command == "render":
        from historyforgeai.application.services.render_job import render_approved_job
        from historyforgeai.infrastructure.persistence.filesystem import FileJobRepository
        from historyforgeai.infrastructure.rendering.ffmpeg import FFmpegRenderer
        work = ROOT / "workspace"
        repo = FileJobRepository(work / "jobs")
        renderer = FFmpegRenderer(config["width"], config["height"], config["fps"])
        try:
            print(render_approved_job(args.job, work, repo, renderer, motion=args.motion))
        except Exception as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            sys.exit(1)
    elif args.command == "image":
        from historyforgeai.application.services.image_candidates import create_candidate
        try:
            if not args.job or not all(ch.isalnum() or ch in "-_" for ch in args.job):
                raise ValueError("Invalid job ID")
            print(create_candidate(ROOT / "workspace" / "jobs" / args.job, args.scene,
                provider=args.provider, source=args.file, model=args.model, allow_paid=args.allow_paid))
        except Exception as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            sys.exit(1)
    elif args.command == "list":
        for file in sorted((ROOT / "workspace" / "jobs").glob("*/manifest.json")):
            data = json.loads(file.read_text(encoding="utf-8"))
            print(f"{data['id']}  {data['status']}  {data['topic']}")
    elif args.command == "topics":
        with (ROOT / "data" / "topics.csv").open(encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                if row.get("status") == "queued":
                    print(row["topic"])

if __name__ == "__main__":
    main()
