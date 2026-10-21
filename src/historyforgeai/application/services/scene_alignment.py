"""Scene-to-narration alignment helpers for human-reviewed cinematic Shorts.

Visual meaning cannot be inferred reliably from filenames or audio durations:
the reviewer must see the exact image beside the narration before rendering.
"""
import hashlib
from pathlib import Path

from historyforgeai.application.services.storyboard import Storyboard
from historyforgeai.domain.models import ShortPlan


IMAGE_FIELDS = ("candidate_image", "source_url", "license", "attribution")


def duplicate_image_groups(storyboard: Storyboard) -> list[list[int]]:
    """Identify repeated *image content*, including copies with different names."""
    groups: dict[str, list[int]] = {}
    for shot in storyboard.shots:
        if not shot.candidate_image:
            continue
        try:
            path = Path(shot.candidate_image).expanduser()
            if not path.is_file():
                continue
            digest = hashlib.sha256()
            with path.open("rb") as image:
                for chunk in iter(lambda: image.read(1024 * 1024), b""):
                    digest.update(chunk)
            groups.setdefault(digest.hexdigest(), []).append(shot.scene_index)
        except OSError:
            continue
    return [indices for indices in groups.values() if len(indices) > 1]


def swap_scene_images(storyboard: Storyboard, first: int, second: int) -> None:
    """Move image and provenance together, retaining each scene's narration.

    A swap always invalidates image approval for both affected scenes.
    """
    by_index = {shot.scene_index: shot for shot in storyboard.shots}
    if first == second:
        raise ValueError("Choose two different scenes to swap")
    if first not in by_index or second not in by_index:
        raise ValueError("Both scene indexes must exist in the storyboard")
    a, b = by_index[first], by_index[second]
    for field in IMAGE_FIELDS:
        left, right = getattr(a, field), getattr(b, field)
        setattr(a, field, right)
        setattr(b, field, left)
    a.status = "pending_review"
    b.status = "pending_review"


def scene_mapping_issues(plan: ShortPlan, storyboard: Storyboard) -> list[str]:
    """Catch stale scene text and missing images before visual approval."""
    issues: list[str] = []
    by_index = {shot.scene_index: shot for shot in storyboard.shots}
    expected = {scene.index for scene in plan.scenes}
    if len(by_index) != len(storyboard.shots) or set(by_index) != expected:
        issues.append("Storyboard scene indexes do not match the script")
    for scene in plan.scenes:
        shot = by_index.get(scene.index)
        if shot is None:
            continue
        if shot.narration.strip() != scene.narration.strip():
            issues.append(f"Scene {scene.index}: storyboard narration differs from script")
        if shot.visual_description.strip() != scene.visual_description.strip():
            issues.append(f"Scene {scene.index}: visual description differs from script")
        if not shot.candidate_image or not Path(shot.candidate_image).expanduser().is_file():
            issues.append(f"Scene {scene.index}: no existing image assigned")
    return issues
