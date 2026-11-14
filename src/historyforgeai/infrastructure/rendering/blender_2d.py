"""Blender-backed hierarchical 2D puppet renderer for approved HistoryForgeAI storyboards.

The approved scene image remains the background. Optional animation/scene_XX.json
files add reviewed, parented PNG/WebP puppet parts. No arbitrary Blender
Python from the storyboard is executed.
"""
import json
import math
import shutil
import subprocess
from pathlib import Path
from typing import Literal

from PIL import Image
from pydantic import BaseModel, ConfigDict, Field, model_validator

from historyforgeai.domain.models import ShortPlan


class PuppetKeyframe(BaseModel):
    """Offsets from bind pose; easing describes arrival at this keyframe."""
    model_config = ConfigDict(extra="forbid")

    t: float = Field(ge=0, le=1)
    dx: float | None = Field(default=None, ge=-2, le=2)
    dy: float | None = Field(default=None, ge=-2, le=2)
    rotation_deg: float | None = Field(default=None, ge=-360, le=360)
    scale: float | None = Field(default=None, gt=0, le=10)
    easing: Literal["linear", "hold", "ease_in", "ease_out", "ease_in_out", "back_out"] = "ease_in_out"

    @model_validator(mode="after")
    def has_change(self):
        if all(getattr(self, key) is None for key in ("dx", "dy", "rotation_deg", "scale")):
            raise ValueError("A puppet keyframe must change an offset, rotation or scale")
        return self


class PuppetPart(BaseModel):
    """One image and joint; bind x/y are normalized absolute canvas coordinates."""
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,48}$")
    asset: str = Field(min_length=1)
    parent: str | None = None
    x: float = Field(default=0.5, ge=-1, le=2)
    y: float = Field(default=0.5, ge=-1, le=2)
    width: float = Field(default=0.5, gt=0, le=3)
    pivot: tuple[float, float] = (0.5, 0.5)
    z: int = Field(default=1, ge=-99, le=99)
    keyframes: list[PuppetKeyframe] = Field(default_factory=list, max_length=60)

    @model_validator(mode="after")
    def validate_part(self):
        if any(not 0 <= value <= 1 for value in self.pivot):
            raise ValueError("Part pivot must be within its image (0..1)")
        times = [keyframe.t for keyframe in self.keyframes]
        if times != sorted(set(times)):
            raise ValueError("Keyframes must have unique, increasing t values")
        return self


class PuppetRig(BaseModel):
    """Version 2 ONLY. The independent-layer format is intentionally unsupported."""
    model_config = ConfigDict(extra="forbid")
    version: Literal[2] = 2
    parts: list[PuppetPart] = Field(default_factory=list, max_length=32)

    @model_validator(mode="after")
    def validate_hierarchy(self):
        by_id = {part.id: part for part in self.parts}
        if len(by_id) != len(self.parts):
            raise ValueError("Puppet part IDs must be unique")
        for part in self.parts:
            if part.parent is not None and part.parent not in by_id:
                raise ValueError(f"Unknown parent {part.parent!r} for {part.id!r}")
            seen = {part.id}
            parent = part.parent
            while parent is not None:
                if parent in seen:
                    raise ValueError("Puppet joint hierarchy contains a cycle")
                seen.add(parent)
                parent = by_id[parent].parent
        return self


def resolve_cutout_asset(job_dir: Path, asset: str) -> Path:
    """Resolve job-local or library: assets, disallowing traversal and symlinks out."""
    job_dir = Path(job_dir).resolve()
    if asset.startswith("library:"):
        root = job_dir.parent.parent.resolve()  # workspace/
        relative = asset[len("library:"):]
    else:
        root = job_dir
        relative = asset
    if not relative or Path(relative).is_absolute():
        raise ValueError("Animation asset paths must be relative")
    candidate = (root / relative).resolve()
    if not candidate.is_relative_to(root):
        raise ValueError("Animation asset must remain inside its job or workspace library")
    if candidate.suffix.lower() not in {".png", ".webp"}:
        raise ValueError("Cutout layers must be transparent PNG or WebP files")
    if not candidate.is_file():
        raise FileNotFoundError(f"Missing cutout asset: {candidate}")
    try:
        with Image.open(candidate) as image:
            if "A" not in image.getbands() and "transparency" not in image.info:
                raise ValueError(f"Cutout asset needs transparency: {candidate}")
            image.verify()
    except (OSError, Image.DecompressionBombError) as exc:
        raise ValueError(f"Unreadable cutout asset: {candidate}") from exc
    return candidate


def build_blender_scene(job_dir: Path, scene, width: int, height: int, fps: int) -> dict:
    """Validate all inputs before launching Blender; use approved image as backdrop."""
    background = Path(scene.image_path or "").expanduser().resolve()
    if not scene.image_path or not background.is_file():
        raise ValueError(f"Scene {scene.index} has no approved background image")
    try:
        with Image.open(background) as image:
            image.verify()
    except (OSError, Image.DecompressionBombError) as exc:
        raise ValueError(f"Unreadable approved background for scene {scene.index}") from exc

    spec_file = Path(job_dir) / "animation" / f"scene_{scene.index:02d}.json"
    rig = PuppetRig.model_validate_json(spec_file.read_text(encoding="utf-8")) if spec_file.exists() else PuppetRig()
    parts = []
    for part in rig.parts:
        data = part.model_dump()
        data["asset"] = str(resolve_cutout_asset(job_dir, part.asset))
        parts.append(data)
    frames = max(1, round(scene.duration_seconds * fps))
    return {
        "version": 2, "width": width, "height": height, "fps": fps,
        "frames": frames, "background": str(background), "parts": parts,
    }

def _frame_count(video: Path) -> int:
    result = subprocess.check_output(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames",
         "-show_entries", "stream=nb_read_frames",
         "-of", "default=noprint_wrappers=1:nokey=1", str(video)],
        text=True, timeout=60,
    ).strip()
    if not result.isdigit():
        raise RuntimeError(f"Could not determine rendered frame count: {video}")
    return int(result)


class Blender2DRenderer:
    """Produce the same clips/scene_XX.mp4 and short.mp4 as FFmpegRenderer."""

    def __init__(self, width=720, height=1280, fps=24):
        if width <= 0 or height <= 0 or fps <= 0:
            raise ValueError("Video dimensions and FPS must be positive")
        self.width, self.height, self.fps = width, height, fps

    def validate(self, plan: ShortPlan, job_dir: Path) -> None:
        """Fail before speech generation if Blender or any cutout asset is missing."""
        if not shutil.which("blender"):
            raise RuntimeError("Blender is required for --visual-style blender-2d (install Blender 3.6+)")
        if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
            raise RuntimeError("ffmpeg and ffprobe are required for Blender rendering")
        from historyforgeai.application.services.illustrated_assets import verify_approved_assets
        for scene in plan.scenes:
            verify_approved_assets(Path(job_dir), scene.index)
            build_blender_scene(Path(job_dir), scene, self.width, self.height, self.fps)

    def render(self, plan: ShortPlan, job_dir: str, audio_path: str | None = None,
               motion: str = "zoom_in") -> str:
        self.validate(plan, Path(job_dir))
        blender = shutil.which("blender")
        job = Path(job_dir).resolve()
        payloads = [build_blender_scene(job, scene, self.width, self.height, self.fps)
                    for scene in plan.scenes]
        clips = job / "clips"
        clips.mkdir(parents=True, exist_ok=True)
        script = Path(__file__).with_name("blender_cutout_scene.py")
        paths = []
        total_frames = 0
        for scene, payload in zip(plan.scenes, payloads):
            index = scene.index
            clip = clips / f"scene_{index:02d}.mp4"
            staging = clips / f"scene_{index:02d}.partial.mp4"
            spec = clips / f"scene_{index:02d}.blender.json"
            frames_dir = clips / f"scene_{index:02d}.frames"
            spec.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            staging.unlink(missing_ok=True)
            if frames_dir.exists():
                shutil.rmtree(frames_dir)
            frames_dir.mkdir()
            try:
                subprocess.run(
                    [blender, "-b", "--factory-startup", "--python", str(script),
                     "--", str(spec), str(frames_dir)],
                    check=True, timeout=max(300, int(scene.duration_seconds * 50)),
                )
                if len(list(frames_dir.glob("frame_*.png"))) != payload["frames"]:
                    raise RuntimeError(f"Blender produced an incomplete frame sequence for scene {index}")
                # Blender 5 removed direct FFmpeg output; system FFmpeg works
                # consistently across Blender versions and produces H.264 clips.
                subprocess.run(
                    ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                     "-framerate", str(self.fps), "-start_number", "1",
                     "-i", str(frames_dir / "frame_%04d.png"),
                     "-frames:v", str(payload["frames"]), "-c:v", "libx264",
                     "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p",
                     str(staging)],
                    check=True, timeout=max(180, int(scene.duration_seconds * 10)),
                )
                if not staging.is_file() or staging.stat().st_size == 0:
                    raise RuntimeError(f"FFmpeg did not encode scene {index}")
                count = _frame_count(staging)
                if count != payload["frames"]:
                    raise RuntimeError(f"Scene {index}: expected {payload['frames']} frames, got {count}")
                staging.replace(clip)
            finally:
                shutil.rmtree(frames_dir, ignore_errors=True)
                staging.unlink(missing_ok=True)
            total_frames += payload["frames"]
            paths.append(clip)

        def ffconcat_quote(path: Path) -> str:
            return str(path.resolve()).replace("\\", "\\\\").replace("'", "'\\''")

        concat = job / "clips.txt"
        concat.write_text("".join(f"file '{ffconcat_quote(path)}'\n" for path in paths), encoding="utf-8")
        silent = job / "silent.mp4"
        output = job / "short.mp4"
        staging_output = job / "short.partial.mp4"
        staging_output.unlink(missing_ok=True)
        subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
             "-f", "concat", "-safe", "0", "-i", str(concat),
             "-c", "copy", str(silent)],
            check=True, timeout=180,
        )
        duration = total_frames / self.fps
        try:
            if audio_path and Path(audio_path).is_file():
                subprocess.run(
                    ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                     "-i", str(silent), "-i", str(audio_path),
                     "-filter_complex", f"[1:a]apad,atrim=duration={duration:.6f}[a]",
                     "-map", "0:v:0", "-map", "[a]", "-c:v", "copy",
                     "-c:a", "aac", "-t", f"{duration:.6f}", str(staging_output)],
                    check=True, timeout=180,
                )
            else:
                shutil.copyfile(silent, staging_output)
            if _frame_count(staging_output) != total_frames:
                raise RuntimeError("Final video frame count differs from the narration-aligned scenes")
            staging_output.replace(output)
        finally:
            staging_output.unlink(missing_ok=True)
        return str(output)
