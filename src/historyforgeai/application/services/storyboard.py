"""Reviewable storyboard, separated from rendering and remote asset providers."""
import json
from pathlib import Path
from PIL import Image
from pydantic import BaseModel, Field
from historyforgeai.domain.models import ShortPlan

class Shot(BaseModel):
    scene_index: int
    narration: str
    visual_description: str
    search_query: str
    character_ids: list[str] = Field(default_factory=list)
    candidate_image: str | None = None
    source_url: str | None = None
    license: str | None = None
    attribution: str | None = None
    status: str = 'pending_review'

class Storyboard(BaseModel):
    topic: str
    shots: list[Shot]

def make_storyboard(plan: ShortPlan, registry) -> Storyboard:
    shots = []
    for scene in plan.scenes:
        image = scene.image_path
        for character_id in scene.character_ids:
            try:
                char = registry.get(character_id)
            except FileNotFoundError:
                continue
            if char.approved and char.canonical_image and Path(char.canonical_image).is_file() and not image:
                image = char.canonical_image
        shots.append(Shot(scene_index=scene.index, narration=scene.narration,
            visual_description=scene.visual_description, search_query=scene.asset_query,
            character_ids=scene.character_ids, candidate_image=image,
            source_url=scene.asset_source_url, license=scene.asset_license,
            attribution=scene.attribution))
    return Storyboard(topic=plan.topic, shots=shots)

def load(path: Path) -> Storyboard:
    return Storyboard.model_validate_json(path.read_text(encoding='utf-8'))

def save(path: Path, storyboard: Storyboard) -> None:
    path.write_text(storyboard.model_dump_json(indent=2), encoding='utf-8')

def apply_approved(plan_path: Path, storyboard_path: Path) -> int:
    storyboard = load(storyboard_path)
    plan = ShortPlan.model_validate_json(plan_path.read_text(encoding='utf-8'))
    by_index = {shot.scene_index: shot for shot in storyboard.shots}
    if len(by_index) != len(storyboard.shots) or set(by_index) != {scene.index for scene in plan.scenes}:
        raise ValueError('Storyboard scene indexes do not match plan')
    for scene in plan.scenes:
        shot = by_index[scene.index]
        if shot.narration.strip() != scene.narration.strip() or shot.visual_description.strip() != scene.visual_description.strip():
            raise ValueError(f'Scene {scene.index} storyboard text differs from approved script; review alignment again')
        if shot.status != 'approved' or not shot.candidate_image or not Path(shot.candidate_image).expanduser().is_file():
            raise ValueError(f'Scene {scene.index} needs an approved, existing image')
        scene.image_path = shot.candidate_image
        scene.asset_source_url = shot.source_url
        scene.asset_license = shot.license
        scene.attribution = shot.attribution
    plan_path.write_text(plan.model_dump_json(indent=2), encoding='utf-8')
    return len(plan.scenes)


def approve_available_images(storyboard: Storyboard) -> tuple[list[int], list[int]]:
    """Bulk-approve existing, readable images; leave invalid scenes unchanged."""
    approved, skipped = [], []
    for shot in storyboard.shots:
        if not shot.candidate_image:
            skipped.append(shot.scene_index)
            continue
        path = Path(shot.candidate_image).expanduser()
        try:
            with Image.open(path) as image:
                image.verify()
        except (OSError, ValueError, Image.DecompressionBombError):
            skipped.append(shot.scene_index)
            continue
        shot.candidate_image = str(path.resolve())
        shot.status = 'approved'
        approved.append(shot.scene_index)
    return approved, skipped


def approve_saved_images(board_path: Path) -> tuple[list[int], list[int]]:
    """Bulk-approve the persisted storyboard without trusting stale UI values."""
    storyboard = load(board_path)
    approved, skipped = approve_available_images(storyboard)
    save(board_path, storyboard)
    return approved, skipped
