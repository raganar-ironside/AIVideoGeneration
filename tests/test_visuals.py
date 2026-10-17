import json
from pathlib import Path
import pytest
from PIL import Image
from historyforgeai.domain.characters import Character
from historyforgeai.domain.models import ShortPlan, Scene
from historyforgeai.infrastructure.persistence.characters import CharacterRegistry
from historyforgeai.application.services.visuals import VisualResolver
from historyforgeai.application.services.timeline import build_timeline
from historyforgeai.infrastructure.rendering.motion import zoompan_filter

def plan():
    return ShortPlan(topic='Rama', title='Rama', narration='Rama speaks', scenes=[
        Scene(index=1,duration_seconds=5,narration='Rama speaks',visual_description='Rama',
              asset_query='Rama',character_ids=['rama'])])

def test_registry_and_reuse(tmp_path):
    image = tmp_path / 'rama.png'
    Image.new('RGB',(40,40),'blue').save(image)
    registry = CharacterRegistry(tmp_path / 'characters')
    registry.save(Character(id='rama',display_name='Rama',universe='ramayana',
                            canonical_image=str(image),approved=True))
    result = VisualResolver(registry).resolve(plan())
    assert result.scenes[0].image_path == str(image)
    assert result.scenes[0].visual_type == 'character_art'

def test_unapproved_character_fails(tmp_path):
    registry = CharacterRegistry(tmp_path)
    registry.save(Character(id='rama',display_name='Rama',universe='ramayana'))
    with pytest.raises(ValueError, match='approved'):
        VisualResolver(registry).resolve(plan())

def test_timeline():
    timeline = build_timeline(plan(),[7.5])
    assert timeline[0]['start'] == 0
    assert timeline[0]['end'] == 7.5

def test_motion():
    assert 'zoompan' in zoompan_filter(720,1280,24,5)
