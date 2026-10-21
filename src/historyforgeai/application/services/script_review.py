"""Human-reviewed script edits and tamper-aware approval for storyboard rendering."""
import hashlib
import json
from pathlib import Path

from historyforgeai.domain.models import ShortPlan


def _fingerprint(plan: ShortPlan) -> str:
    """Track narration and visual intent, not render-derived scene durations."""
    fields = {
        "title": plan.title,
        "scenes": [
            {"index": s.index, "narration": s.narration,
             "visual_description": s.visual_description, "asset_query": s.asset_query}
            for s in plan.scenes
        ],
    }
    return hashlib.sha256(json.dumps(fields, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def script_approved(job_dir: Path) -> bool:
    plan_path = job_dir / "scene_plan.json"
    approval_path = job_dir / "script_approval.json"
    if not plan_path.is_file() or not approval_path.is_file():
        return False
    try:
        plan = ShortPlan.model_validate_json(plan_path.read_text(encoding="utf-8"))
        record = json.loads(approval_path.read_text(encoding="utf-8"))
        return record.get("fingerprint") == _fingerprint(plan)
    except (ValueError, OSError, KeyError, TypeError):
        return False


def save_script_edits(job_dir: Path, edits: dict[int, dict[str, str]]) -> list[int]:
    """Save selected scene edits, back up the first draft, and reset affected images."""
    from historyforgeai.application.services.storyboard import load, save
    plan_path = job_dir / "scene_plan.json"
    board_path = job_dir / "storyboard.json"
    plan = ShortPlan.model_validate_json(plan_path.read_text(encoding="utf-8"))
    board = load(board_path)
    by_index = {shot.scene_index: shot for shot in board.shots}
    if len(by_index) != len(plan.scenes) or set(by_index) != {s.index for s in plan.scenes}:
        raise ValueError("Storyboard and script scene indexes differ")
    unknown = set(edits) - set(by_index)
    if unknown:
        raise ValueError(f"Unknown scene indexes: {sorted(unknown)}")
    changes = []
    for scene in plan.scenes:
        values = edits.get(scene.index, {})
        for field in values:
            if field not in ("narration", "visual_description", "asset_query"):
                raise ValueError(f"Unsupported script field: {field}")
        if "narration" in values and not values["narration"].strip():
            raise ValueError(f"Scene {scene.index} narration cannot be empty")
        if any(getattr(scene, field) != value for field, value in values.items()):
            changes.append(scene.index)
    if not changes:
        return []
    backup = job_dir / "original_scene_plan.json"
    if not backup.exists():
        backup.write_bytes(plan_path.read_bytes())
    for scene in plan.scenes:
        if scene.index not in changes:
            continue
        shot = by_index[scene.index]
        values = edits[scene.index]
        for field, value in values.items():
            setattr(scene, field, value)
        shot.narration = scene.narration
        shot.visual_description = scene.visual_description
        shot.search_query = scene.asset_query
        shot.status = "pending_review"
    plan.narration = " ".join(s.narration.strip() for s in plan.scenes)
    (job_dir / "script_approval.json").unlink(missing_ok=True)
    # Remove stale audio so legacy rendering cannot reuse the previous script's speech.
    for audio in [job_dir / "narration.wav", *job_dir.glob("narration_scene_*.wav"),
                  *job_dir.glob("narration_padded_*.wav")]:
        audio.unlink(missing_ok=True)
    (job_dir / 'timeline.json').unlink(missing_ok=True)
    save(board_path, board)
    plan_path.write_text(plan.model_dump_json(indent=2), encoding="utf-8")
    return changes


def approve_script(job_dir: Path) -> None:
    plan = ShortPlan.model_validate_json((job_dir / "scene_plan.json").read_text(encoding="utf-8"))
    if not all(s.narration.strip() for s in plan.scenes):
        raise ValueError("All scenes need narration before approval")
    (job_dir / "script_approval.json").write_text(
        json.dumps({"fingerprint": _fingerprint(plan)}, indent=2), encoding="utf-8")
