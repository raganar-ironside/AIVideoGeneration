import json
from pathlib import Path
from historyforgeai.domain.characters import Character

class CharacterRegistry:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, character_id: str) -> Path:
        if not character_id or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789_-' for c in character_id) or not character_id[0].isalpha():
            raise ValueError('Invalid character id')
        return self.root / f'{character_id}.json'

    def save(self, character: Character) -> Path:
        target = self._path(character.id)
        target.write_text(character.model_dump_json(indent=2), encoding='utf-8')
        return target

    def get(self, character_id: str) -> Character:
        return Character.model_validate_json(self._path(character_id).read_text(encoding='utf-8'))

    def list(self) -> list[Character]:
        return [Character.model_validate_json(f.read_text(encoding='utf-8')) for f in sorted(self.root.glob('*.json'))]
