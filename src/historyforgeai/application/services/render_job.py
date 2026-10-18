"""Render an approved storyboard, optionally synthesizing narration after approval."""
import json
import shutil
import subprocess
from pathlib import Path

from historyforgeai.application.services.storyboard import apply_approved
from historyforgeai.application.services.timeline import build_timeline
from historyforgeai.domain.models import JobStatus, ShortPlan


def render_approved_job(job_id: str, workspace: Path, repository, renderer,
                        motion: str = "zoom_in", speech=None, scene_audio: bool = False) -> Path:
    """Validate all approvals before any speech synthesis or rendering.

    With speech=None, retain the legacy behavior of reusing narration.wav if present.
    With speech provided, synthesize fresh narration after storyboard approval.
    """
    if not job_id or not all(c.isalnum() or c in "-_" for c in job_id):
        raise ValueError("Invalid job ID")
    folder = Path(workspace) / "jobs" / job_id
    plan_path = folder / "scene_plan.json"
    board_path = folder / "storyboard.json"
    if not plan_path.is_file() or not board_path.is_file():
        raise FileNotFoundError("Both scene_plan.json and storyboard.json are required")
    job = repository.load(job_id)
    apply_approved(plan_path, board_path)
    plan = ShortPlan.model_validate_json(plan_path.read_text(encoding="utf-8"))
    narration = folder / "narration.wav"
    if speech is not None:
        if scene_audio:
            if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
                raise RuntimeError("ffmpeg and ffprobe are required for scene audio")
            durations = []
            padded = []
            for scene in plan.scenes:
                part = folder / f"narration_scene_{scene.index:02d}.wav"
                if not speech.synthesize(scene.narration, str(part)):
                    raise RuntimeError(f"Speech generation failed for scene {scene.index}")
                probe = subprocess.check_output(
                    ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                     "-of", "default=noprint_wrappers=1:nokey=1", str(part)], text=True)
                duration = float(probe.strip()) + 0.25
                pad = folder / f"narration_padded_{scene.index:02d}.wav"
                subprocess.run(
                    ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                     "-i", str(part), "-af", f"apad=whole_dur={duration:.3f}",
                     "-t", f"{duration:.3f}", "-ar", "24000", "-ac", "1", str(pad)],
                    check=True)
                durations.append(duration)
                padded.append(pad)
            for scene, duration in zip(plan.scenes, durations):
                scene.duration_seconds = duration
            concat = folder / "audio_concat.txt"
            concat.write_text("".join(f"file '{p.resolve()}'\n" for p in padded), encoding="utf-8")
            subprocess.run(
                ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "concat",
                 "-safe", "0", "-i", str(concat), "-ar", "24000", "-ac", "1", str(narration)],
                check=True)
            (folder / "timeline.json").write_text(
                json.dumps(build_timeline(plan, durations), indent=2), encoding="utf-8")
            plan_path.write_text(plan.model_dump_json(indent=2), encoding="utf-8")
        elif not speech.synthesize(plan.narration, str(narration)):
            raise RuntimeError("Speech generation failed")
        if not narration.is_file() or narration.stat().st_size <= 44:
            raise RuntimeError("Speech generation did not create valid narration")
    audio = str(narration) if narration.is_file() else None
    output = renderer.render(plan, str(folder), audio, motion=motion)
    job.video_path = output
    job.status = JobStatus.RENDERED
    repository.save(job)
    return Path(output)
