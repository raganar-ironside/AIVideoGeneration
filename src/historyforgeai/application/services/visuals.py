from pathlib import Path
from historyforgeai.domain.models import ShortPlan

class VisualResolver:
    """Use approved character art, never silently replace an unapproved character."""
    def __init__(self, registry):
        self.registry = registry

    def resolve(self, plan: ShortPlan) -> ShortPlan:
        for scene in plan.scenes:
            if scene.image_path and Path(scene.image_path).is_file():
                continue
            for character_id in scene.character_ids:
                character = self.registry.get(character_id)
                if not character.approved or not character.canonical_image:
                    raise ValueError(f'Character {character_id} requires an approved canonical image')
                image = Path(character.canonical_image)
                if not image.is_file():
                    raise FileNotFoundError(f'Character image missing: {image}')
                scene.image_path = str(image)
                scene.visual_type = 'character_art'
                break
        return plan
