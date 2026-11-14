"""Review-first multi-character puppet scene builder.

Character art and timeline edits live in a draft until explicitly approved.
Publishing hashes both art and the authored scene; custom motion JSON files
are also pinned by SHA-256. Existing approved scenes stay untouched on draft
errors. This is a local workflow, not an AI image generator.
"""
import hashlib
import json
import shutil
from pathlib import Path

from PIL import Image, ImageOps

from historyforgeai.application.services.motion_library import motion_source_path
from historyforgeai.application.services.puppet_templates import PUPPET_PARTS, puppet_template
from historyforgeai.application.services.puppet_timeline import (
    CharacterInstance, MotionAction, MultiCharacterScene, compile_multi_character_scene,
)
from historyforgeai.domain.models import ShortPlan
from historyforgeai.infrastructure.rendering.blender_2d import resolve_cutout_asset


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _draft_dir(job: Path, scene: int) -> Path:
    if not isinstance(scene, int) or scene < 1:
        raise ValueError("Scene index must be positive")
    return Path(job).resolve() / "animation" / "multi_drafts" / f"scene_{scene:02d}"


def _live_path(job: Path, scene: int) -> Path:
    return Path(job).resolve() / "animation" / f"scene_{scene:02d}.json"


def _asset_root(job: Path, scene: int) -> Path:
    return Path(job).resolve() / "animation" / "assets" / f"scene_{scene:02d}" / "characters"


def _scene_duration(job: Path, scene: int) -> float:
    plan = ShortPlan.model_validate_json(
        (Path(job).resolve() / "scene_plan.json").read_text(encoding="utf-8")
    )
    match = next((item for item in plan.scenes if item.index == scene), None)
    if match is None:
        raise ValueError(f"Scene {scene} does not exist in the scene plan")
    return match.duration_seconds


def _check_image(path: Path):
    if not path.is_file() or path.stat().st_size > 20 * 1024 * 1024:
        raise ValueError(f"Missing or oversized puppet PNG: {path.name}")
    if path.suffix.lower() != ".png":
        raise ValueError("Puppet parts must be PNGs")
    with Image.open(path) as image:
        image.verify()
    with Image.open(path) as image:
        if "A" not in image.getbands() and "transparency" not in image.info:
            raise ValueError(f"Part {path.name} needs transparency")


def _save_draft(job: Path, scene: int, payload: dict) -> Path:
    folder = _draft_dir(job, scene)
    folder.mkdir(parents=True, exist_ok=True)
    dest = folder / "scene.json"
    temp = folder / "scene.partial.json"
    try:
        temp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        temp.replace(dest)
    finally:
        temp.unlink(missing_ok=True)
    return dest


def load_multi_draft(job: Path, scene: int) -> dict | None:
    path = _draft_dir(job, scene) / "scene.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def _ensure_draft(job: Path, scene: int) -> dict:
    job = Path(job).resolve()
    draft = load_multi_draft(job, scene)
    if draft is not None:
        return draft
    live = _live_path(job, scene)
    if live.is_file():
        existing = json.loads(live.read_text(encoding="utf-8"))
        if existing.get("version") == 3:
            from historyforgeai.application.services.illustrated_assets import verify_approved_assets
            verify_approved_assets(job, scene)
            spec = MultiCharacterScene.model_validate(existing)
            for char in spec.characters:
                target = _draft_dir(job, scene) / "characters" / char.id
                target.mkdir(parents=True, exist_ok=True)
                for part in char.parts:
                    source = resolve_cutout_asset(job, part.asset)
                    shutil.copyfile(source, target / f"{part.id}.png")
            _save_draft(job, scene, existing)
            return existing
    return {"version": 3, "characters": [], "timeline": []}


def stage_character(job: Path, scene: int, character_id: str, source: Path, *,
                    x: float = .5, y: float = .5, scale: float = 1,
                    depth: int = 0) -> Path:
    """Stage one independently rigged character, without touching live scenes."""
    job = Path(job).resolve()
    _scene_duration(job, scene)
    draft = _ensure_draft(job, scene)
    if any(c["id"] == character_id for c in draft["characters"]):
        raise ValueError(f"Character {character_id!r} is already in the scene")
    source = Path(source).expanduser().resolve()
    if not source.is_dir():
        raise ValueError("Source must be a directory of 12 named transparent PNGs")
    # Validate the instance before writing any draft files.
    template = puppet_template(scene)["parts"]
    for part in template:
        part["keyframes"] = []
        part["asset"] = (
            f"animation/assets/scene_{scene:02d}/characters/{character_id}/{part['id']}.png"
        )
    character = CharacterInstance.model_validate({
        "id": character_id, "x": x, "y": y, "scale": scale,
        "depth": depth, "parts": template,
    })
    for name in PUPPET_PARTS:
        _check_image(source / f"{name}.png")
    updated = dict(draft)
    updated["characters"] = [*draft["characters"], character.model_dump()]
    MultiCharacterScene.model_validate(updated)
    dest = _draft_dir(job, scene) / "characters" / character_id
    pending = dest.with_name(dest.name + ".pending")
    if pending.exists():
        shutil.rmtree(pending)
    pending.mkdir(parents=True, exist_ok=True)
    try:
        for name in PUPPET_PARTS:
            shutil.copyfile(source / f"{name}.png", pending / f"{name}.png")
        if dest.exists():
            raise FileExistsError(f"Staged assets already exist for {character_id}")
        pending.rename(dest)
        _save_draft(job, scene, updated)
    except Exception:
        if dest.exists() and not any(c["id"] == character_id for c in draft["characters"]):
            shutil.rmtree(dest)
        raise
    finally:
        if pending.exists():
            shutil.rmtree(pending)
    return _draft_dir(job, scene) / "scene.json"


def remove_character(job: Path, scene: int, character_id: str) -> Path:
    draft = _ensure_draft(job, scene)
    if not any(c["id"] == character_id for c in draft["characters"]):
        raise ValueError(f"No character {character_id!r} in draft")
    updated = dict(draft)
    updated["characters"] = [c for c in draft["characters"] if c["id"] != character_id]
    updated["timeline"] = [a for a in draft["timeline"] if a["character"] != character_id]
    path = _save_draft(job, scene, updated)
    shutil.rmtree(_draft_dir(job, scene) / "characters" / character_id, ignore_errors=True)
    return path


def add_motion_action(job: Path, scene: int, *, character: str, motion: str,
                      start: float, duration: float, repeat: int = 1,
                      intensity: float = 1, direction: int = 1,
                      distance: float = 0) -> Path:
    draft = _ensure_draft(job, scene)
    action = MotionAction.model_validate({
        "character": character, "motion": motion, "start": start,
        "duration": duration, "repeat": repeat, "intensity": intensity,
        "direction": direction, "distance": distance,
    })
    updated = dict(draft)
    updated["timeline"] = [*draft["timeline"], action.model_dump()]
    spec = MultiCharacterScene.model_validate(updated)
    compile_multi_character_scene(spec, job, _scene_duration(job, scene))
    return _save_draft(job, scene, updated)


def remove_motion_action(job: Path, scene: int, index: int) -> Path:
    draft = _ensure_draft(job, scene)
    if index < 0 or index >= len(draft["timeline"]):
        raise ValueError("Action index out of range")
    updated = dict(draft)
    updated["timeline"] = [
        a for i, a in enumerate(draft["timeline"]) if i != index
    ]
    return _save_draft(job, scene, updated)


def approve_multi_scene(job: Path, scene: int) -> Path:
    """Publish a reviewed v3 scene with art and motion hashes."""
    job = Path(job).resolve()
    draft = load_multi_draft(job, scene)
    if draft is None:
        raise ValueError("No multi-character draft to approve")
    spec = MultiCharacterScene.model_validate(draft)
    compile_multi_character_scene(spec, job, _scene_duration(job, scene))
    draft_dir = _draft_dir(job, scene)
    source_root = draft_dir / "characters"
    target_root = _asset_root(job, scene)
    publishing = target_root.with_name(target_root.name + ".publishing")
    backup = target_root.with_name(target_root.name + ".backup")
    if publishing.exists() or backup.exists():
        raise RuntimeError("Previous interrupted publish needs manual inspection")
    assets = {}
    for char in spec.characters:
        for part in char.parts:
            expected = f"animation/assets/scene_{scene:02d}/characters/{char.id}/{part.id}.png"
            if part.asset != expected:
                raise ValueError(f"Unapproved or nonstandard asset path for {char.id}/{part.id}")
            source = source_root / char.id / f"{part.id}.png"
            _check_image(source)
            assets[expected] = _digest(source)
    motions = {}
    for action in spec.timeline:
        source = motion_source_path(job, action.motion)
        if source is not None:
            motions[action.motion] = _digest(source)
    # Revalidate custom clips before replacing any approved scene.
    compile_multi_character_scene(spec, job, _scene_duration(job, scene))
    publishing.mkdir(parents=True, exist_ok=False)
    try:
        for char in spec.characters:
            target = publishing / char.id
            target.mkdir()
            for part in char.parts:
                shutil.copyfile(source_root / char.id / f"{part.id}.png",
                                target / f"{part.id}.png")
        target_root.parent.mkdir(parents=True, exist_ok=True)
        live = _live_path(job, scene)
        old_spec = live.read_bytes() if live.is_file() else None
        approval = job / "animation" / "approved" / f"scene_{scene:02d}.json"
        old_approval = approval.read_bytes() if approval.is_file() else None
        moved_old = False
        moved_new = False
        try:
            if target_root.exists():
                target_root.rename(backup)
                moved_old = True
            publishing.rename(target_root)
            moved_new = True
            live.parent.mkdir(parents=True, exist_ok=True)
            temp = live.with_suffix(".partial.json")
            temp.write_text(spec.model_dump_json(indent=2), encoding="utf-8")
            temp.replace(live)
            approval.parent.mkdir(parents=True, exist_ok=True)
            record = {
                "format": "puppet-v3", "scene_index": scene,
                "spec_sha256": _digest(live), "asset_sha256": assets,
                "motion_sha256": motions,
            }
            temp_approval = approval.with_suffix(".partial.json")
            temp_approval.write_text(json.dumps(record, indent=2), encoding="utf-8")
            temp_approval.replace(approval)
        except Exception:
            if moved_new and target_root.exists():
                shutil.rmtree(target_root)
            if moved_old and backup.exists():
                backup.rename(target_root)
            if old_spec is None:
                live.unlink(missing_ok=True)
            else:
                live.write_bytes(old_spec)
            if old_approval is None:
                approval.unlink(missing_ok=True)
            else:
                approval.write_bytes(old_approval)
            raise
        if backup.exists():
            shutil.rmtree(backup)
    finally:
        if publishing.exists():
            shutil.rmtree(publishing)
    return _live_path(job, scene)


def preview_multi_scene(job: Path, scene: int, width: int = 360,
                        height: int = 640) -> Path:
    """Static bind-pose preview. Does not render motion or joint rotations."""
    job = Path(job).resolve()
    draft = load_multi_draft(job, scene)
    if draft is None:
        raise ValueError("No multi-character draft")
    spec = MultiCharacterScene.model_validate(draft)
    plan = ShortPlan.model_validate_json((job / "scene_plan.json").read_text(encoding="utf-8"))
    item = next((s for s in plan.scenes if s.index == scene), None)
    if item and item.image_path and Path(item.image_path).is_file():
        with Image.open(item.image_path) as image:
            canvas = ImageOps.fit(image.convert("RGBA"), (width, height))
    else:
        canvas = Image.new("RGBA", (width, height), (40, 51, 68, 255))
    ordered = []
    for char in spec.characters:
        for part in char.parts:
            ordered.append((char.depth * 20 + part.z, char, part))
    for _, char, part in sorted(ordered, key=lambda item: item[0]):
        source = _draft_dir(job, scene) / "characters" / char.id / f"{part.id}.png"
        with Image.open(source) as image:
            sprite = image.convert("RGBA")
        px_width = max(1, round(width * part.width * char.scale))
        px_height = max(1, round(px_width * sprite.height / sprite.width))
        sprite = sprite.resize((px_width, px_height), Image.Resampling.LANCZOS)
        x = (char.x + (part.x - .5) * char.scale) * width
        y = (char.y + (part.y - .5) * char.scale) * height
        left = round(x - part.pivot[0] * px_width)
        top = round(y - part.pivot[1] * px_height)
        overlay = Image.new("RGBA", (width, height))
        overlay.paste(sprite, (left, top))
        canvas = Image.alpha_composite(canvas, overlay)
    output = _draft_dir(job, scene) / "preview.png"
    canvas.convert("RGB").save(output)
    return output
