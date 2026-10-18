from pathlib import Path

from PIL import Image

from historyforgeai.bootstrap import build
from historyforgeai.application.services.script_review import (
    approve_script, save_script_edits, script_approved,
)
from historyforgeai.application.services.storyboard import make_storyboard, save, load
from historyforgeai.domain.models import ShortPlan
from historyforgeai.infrastructure.persistence.characters import CharacterRegistry


def setup(tmp_path):
    pipeline = build("mock", workspace=tmp_path)
    job = pipeline.run("Rajendra Chola", render=False)
    folder = tmp_path / "jobs" / job.id
    plan = ShortPlan.model_validate_json((folder / "scene_plan.json").read_text())
    board = make_storyboard(plan, CharacterRegistry(tmp_path / "characters"))
    image = folder / "scene.png"
    Image.new("RGB", (16, 16)).save(image)
    for shot in board.shots:
        shot.candidate_image = str(image)
        shot.status = "approved"
    save(folder / "storyboard.json", board)
    return folder, plan


def test_edit_updates_scene_and_full_narration_and_resets_only_changed_image(tmp_path):
    folder, plan = setup(tmp_path)
    approve_script(folder)
    (folder / "narration.wav").write_bytes(b"old audio")
    edits = {2: {"narration": "सुधारा हुआ वर्णन", "visual_description": "Updated visual"}}
    assert save_script_edits(folder, edits) == [2]
    current = ShortPlan.model_validate_json((folder / "scene_plan.json").read_text())
    assert current.scenes[1].narration == "सुधारा हुआ वर्णन"
    assert current.scenes[0].narration == plan.scenes[0].narration
    assert current.narration == " ".join(s.narration.strip() for s in current.scenes)
    board = load(folder / "storyboard.json")
    assert board.shots[1].status == "pending_review"
    assert board.shots[0].status == "approved"
    assert board.shots[1].narration == "सुधारा हुआ वर्णन"
    assert (folder / "original_scene_plan.json").exists()
    assert not (folder / "narration.wav").exists()
    assert not script_approved(folder)
    approve_script(folder)
    assert script_approved(folder)


def test_direct_script_modification_invalidates_approval(tmp_path):
    folder, plan = setup(tmp_path)
    approve_script(folder)
    assert script_approved(folder)
    plan.scenes[0].narration = "Modified outside the UI"
    (folder / "scene_plan.json").write_text(plan.model_dump_json())
    assert not script_approved(folder)


def test_noop_edit_preserves_approval(tmp_path):
    folder, plan = setup(tmp_path)
    approve_script(folder)
    assert save_script_edits(folder, {1: {"narration": plan.scenes[0].narration}}) == []
    assert script_approved(folder)
