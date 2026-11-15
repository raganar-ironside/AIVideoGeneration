"""Content-bound approval for Blender draft previews."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from historyforgeai.infrastructure.rendering.blender_2d import build_blender_scene
from historyforgeai.render_preview import file_sha256


def preview_fingerprint(job_dir: Path, plan) -> str:
    """Hash the approved plan, animation payloads and image contents."""
    job_dir = Path(job_dir).resolve()
    data = []
    for scene in plan.scenes:
        payload = build_blender_scene(job_dir, scene, 540, 960, 24)
        assets = [payload["background"]] + [part["asset"] for part in payload["parts"]]
        data.append({"payload": payload, "asset_hashes": [file_sha256(p) for p in assets]})
    serialized = json.dumps(data, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def preview_is_current(job_dir: Path, fingerprint: str) -> bool:
    path = Path(job_dir) / "preview_fingerprint.json"
    if not path.is_file():
        return False
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("fingerprint") == fingerprint
    except (ValueError, OSError):
        return False


def approve_preview(job_dir: Path, fingerprint: str) -> None:
    job_dir = Path(job_dir)
    preview = job_dir / "short_preview.mp4"
    if not preview.is_file() or preview.stat().st_size == 0 or not preview_is_current(job_dir, fingerprint):
        raise ValueError("Generate a preview before approving it")
    (job_dir / "preview_approval.json").write_text(
        json.dumps({"fingerprint": fingerprint, "preview_hash": file_sha256(preview)}),
        encoding="utf-8",
    )


def is_preview_approved(job_dir: Path, fingerprint: str) -> bool:
    job_dir = Path(job_dir)
    path = job_dir / "preview_approval.json"
    preview = job_dir / "short_preview.mp4"
    if not path.is_file() or not preview.is_file():
        return False
    try:
        saved = json.loads(path.read_text(encoding="utf-8"))
        return preview_is_current(job_dir, fingerprint) and saved.get("fingerprint") == fingerprint and saved.get("preview_hash") == file_sha256(preview)
    except (OSError, ValueError, TypeError):
        return False
