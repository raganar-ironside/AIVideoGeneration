"""Regression coverage for saved-state bulk approval and applying a scene plan."""
from PIL import Image

from historyforgeai.application.services.storyboard import (
    Shot, Storyboard, approve_saved_images, apply_approved, load, save,
)
from historyforgeai.domain.models import Scene, ShortPlan


def test_bulk_approval_keeps_uploaded_paths_and_apply_succeeds(tmp_path):
    job = tmp_path / "job"
    job.mkdir()
    assets = job / "assets"
    assets.mkdir()
    shots = []
    scenes = []
    for index in range(1, 9):
        path = assets / f"candidate_scene_{index:02d}.jpg"
        Image.new("RGB", (60, 90), (index * 20, 0, 0)).save(path)
        narration = f"Narration {index}"
        visual = f"Visual {index}"
        shots.append(Shot(
            scene_index=index, narration=narration,
            visual_description=visual, search_query="temple",
            candidate_image=str(path), status="pending_review",
        ))
        scenes.append(Scene(
            index=index, duration_seconds=6,
            narration=narration, visual_description=visual,
            asset_query="temple",
        ))
    board_path = job / "storyboard.json"
    plan_path = job / "scene_plan.json"
    save(board_path, Storyboard(topic="Test", shots=shots))
    plan_path.write_text(
        ShortPlan(topic="Test", title="Temple", narration=" ".join(
            scene.narration for scene in scenes
        ), scenes=scenes).model_dump_json(indent=2),
        encoding="utf-8",
    )

    # A stale Streamlit path widget may contain empty text, but bulk approval
    # must use the saved board, not the stale widget value.
    stale_widget_paths = {f"path{index}": "" for index in range(1, 9)}
    assert all(value == "" for value in stale_widget_paths.values())

    approved, skipped = approve_saved_images(board_path)
    assert approved == list(range(1, 9))
    assert skipped == []
    assert all(shot.status == "approved" for shot in load(board_path).shots)
    assert apply_approved(plan_path, board_path) == 8

    applied = ShortPlan.model_validate_json(plan_path.read_text(encoding="utf-8"))
    for index, scene in enumerate(applied.scenes, 1):
        assert scene.image_path == str(assets / f"candidate_scene_{index:02d}.jpg")


def test_bulk_approval_skips_missing_without_erasing_other_images(tmp_path):
    job = tmp_path / "job"
    job.mkdir()
    image = job / "valid.jpg"
    Image.new("RGB", (30, 30)).save(image)
    board_path = job / "storyboard.json"
    save(board_path, Storyboard(topic="Test", shots=[
        Shot(scene_index=1, narration="One", visual_description="One",
             search_query="temple", candidate_image=str(image)),
        Shot(scene_index=2, narration="Two", visual_description="Two",
             search_query="temple", candidate_image=None),
    ]))
    approved, skipped = approve_saved_images(board_path)
    assert approved == [1]
    assert skipped == [2]
    board = load(board_path)
    assert board.shots[0].candidate_image == str(image)
    assert board.shots[0].status == "approved"
    assert board.shots[1].candidate_image is None


def test_scene_review_widgets_do_not_mix_session_state_with_defaults():
    """Prevent Streamlit's 'default value and Session State API' warning."""
    import ast
    from pathlib import Path

    app = Path(__file__).resolve().parents[1] / "src/historyforgeai/interfaces/storyboard_app.py"
    tree = ast.parse(app.read_text(encoding="utf-8"))
    checked = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not (isinstance(func, ast.Attribute) and
                func.attr in {"text_input", "selectbox"}):
            continue
        labels = [arg.value for arg in node.args if isinstance(arg, ast.Constant)
                  and isinstance(arg.value, str)]
        if not labels or labels[0] not in {
            "Approved local image path", "Source URL", "License / usage rights",
            "Attribution", "Review status",
        }:
            continue
        kwargs = {keyword.arg for keyword in node.keywords}
        assert "key" in kwargs
        assert "value" not in kwargs
        assert "index" not in kwargs
        checked += 1
    assert checked == 5
