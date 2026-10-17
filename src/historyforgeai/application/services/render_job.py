"""Render an existing, fully approved storyboard without creating a new job."""
from pathlib import Path

from historyforgeai.application.services.storyboard import apply_approved
from historyforgeai.domain.models import JobStatus, ShortPlan


def render_approved_job(job_id: str, workspace: Path, repository, renderer, motion: str = "zoom_in") -> Path:
    """Validate approval before touching the plan or invoking FFmpeg.

    Uses existing narration.wav when available. This is scene-level rendering;
    callers must ensure the audio matches the approved plan's timing.
    """
    if not job_id or not all(c.isalnum() or c in "-_" for c in job_id):
        raise ValueError("Invalid job ID")
    folder = Path(workspace) / "jobs" / job_id
    plan_path = folder / "scene_plan.json"
    board_path = folder / "storyboard.json"
    if not plan_path.is_file() or not board_path.is_file():
        raise FileNotFoundError("Both scene_plan.json and storyboard.json are required")
    job = repository.load(job_id)
    # apply_approved validates *all* scenes before writing the plan.
    apply_approved(plan_path, board_path)
    plan = ShortPlan.model_validate_json(plan_path.read_text(encoding="utf-8"))
    narration = folder / "narration.wav"
    audio = str(narration) if narration.is_file() else None
    output = renderer.render(plan, str(folder), audio, motion=motion)
    job.video_path = output
    job.status = JobStatus.RENDERED
    repository.save(job)
    return Path(output)
