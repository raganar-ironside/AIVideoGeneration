"""Cross-platform Blender/FFmpeg discovery and deterministic preview render profiles.

This module has no Blender dependency and works under native Windows, Linux and WSL.
Integrate these profiles with the existing Blender render entry point before exposing
approval controls in Streamlit.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


@dataclass(frozen=True)
class RenderProfile:
    name: str
    width: int
    height: int
    fps: int = 24
    samples: int = 16

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0 or self.fps <= 0 or self.samples <= 0:
            raise ValueError("Render dimensions, frame rate and samples must be positive")


PREVIEW = RenderProfile("preview", 540, 960, samples=8)
FINAL = RenderProfile("final", 1080, 1920, samples=32)


def find_executable(name: str, env_var: str | None = None) -> Path:
    """Find an executable, respecting explicit overrides and native Windows installs."""
    override = os.environ.get(env_var, "").strip().strip('"') if env_var else ""
    if override:
        path = Path(override).expanduser()
        if not path.is_file():
            raise FileNotFoundError(f"{env_var} points to a missing file: {path}")
        return path.resolve()

    found = shutil.which(name)
    if found:
        return Path(found).resolve()

    if sys.platform == "win32" and name.lower() == "blender":
        base = Path(os.environ.get("PROGRAMFILES", r"C:\Program Files")) / "Blender Foundation"
        candidates = sorted(base.glob("Blender */blender.exe"), reverse=True)
        if candidates:
            return candidates[0].resolve()
    raise FileNotFoundError(
        f"{name} not found; install it or set {env_var or (name.upper() + '_PATH')}"
    )


def blender_path() -> Path:
    return find_executable("blender", "BLENDER_PATH")


def ffmpeg_path() -> Path:
    return find_executable("ffmpeg", "FFMPEG_PATH")


def apply_blender_profile(scene: object, profile: RenderProfile) -> None:
    """Configure a bpy scene without importing bpy in the calling Python process."""
    scene.render.resolution_x = profile.width
    scene.render.resolution_y = profile.height
    scene.render.resolution_percentage = 100
    scene.render.fps = profile.fps
    if hasattr(scene, "eevee") and hasattr(scene.eevee, "taa_render_samples"):
        scene.eevee.taa_render_samples = profile.samples


def scene_cache_key(
    scene_spec: dict, asset_hashes: dict[str, str], profile: RenderProfile,
    renderer_version: str,
) -> str:
    """Key scene output by all declared inputs, including quality and renderer version.

    Callers must hash the *contents* of each referenced image/audio asset.
    """
    payload = {
        "scene": scene_spec,
        "assets": asset_hashes,
        "profile": vars(profile),
        "renderer_version": renderer_version,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_blender(script: str | Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Invoke Blender with argument arrays (never shell=True), including paths with spaces."""
    return subprocess.run(
        [str(blender_path()), "--background", "--python", str(Path(script).resolve()),
         "--", *map(str, args)],
        check=True, text=True, capture_output=True,
    )
