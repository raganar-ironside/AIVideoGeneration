from PIL import Image
import pytest

from historyforgeai.application.services.scene_alignment import (
    duplicate_image_groups, scene_mapping_issues, swap_scene_images,
)
from historyforgeai.application.services.storyboard import Shot, Storyboard
from historyforgeai.domain.models import Scene, ShortPlan


def shot(index, image, narration=None):
    return Shot(
        scene_index=index,
        narration=narration or f"Narration {index}",
        visual_description=f"Visual {index}",
        search_query="temple",
        candidate_image=str(image) if image else None,
        status="approved",
        source_url=f"https://example.org/{index}",
        attribution=f"Author {index}",
    )


def test_duplicate_detection_uses_image_content_not_filename(tmp_path):
    image1 = tmp_path / "a.png"
    image2 = tmp_path / "renamed.png"
    image3 = tmp_path / "different.png"
    Image.new("RGB", (20, 20), "red").save(image1)
    image2.write_bytes(image1.read_bytes())
    Image.new("RGB", (20, 20), "blue").save(image3)
    board = Storyboard(topic="Cholas", shots=[
        shot(1, image1), shot(2, image2), shot(3, image3), shot(4, None)
    ])
    assert duplicate_image_groups(board) == [[1, 2]]


def test_swap_moves_provenance_but_not_narration(tmp_path):
    a = tmp_path / "king.png"
    b = tmp_path / "temple.png"
    board = Storyboard(topic="Cholas", shots=[shot(1, a), shot(2, b)])
    swap_scene_images(board, 1, 2)
    assert board.shots[0].candidate_image == str(b)
    assert board.shots[1].candidate_image == str(a)
    assert board.shots[0].source_url == "https://example.org/2"
    assert board.shots[1].attribution == "Author 1"
    assert board.shots[0].narration == "Narration 1"
    assert [s.status for s in board.shots] == ["pending_review", "pending_review"]


def test_swap_rejects_bad_indices():
    board = Storyboard(topic="Cholas", shots=[shot(1, None), shot(2, None)])
    with pytest.raises(ValueError):
        swap_scene_images(board, 1, 1)
    with pytest.raises(ValueError):
        swap_scene_images(board, 1, 3)


def test_scene_mapping_reports_stale_text_and_missing_image(tmp_path):
    existing = tmp_path / "scene.png"
    Image.new("RGB", (10, 10)).save(existing)
    plan = ShortPlan(topic="Cholas", title="Temple", narration="A B", scenes=[
        Scene(index=1, duration_seconds=2, narration="A", visual_description="Visual 1", asset_query="temple"),
        Scene(index=2, duration_seconds=2, narration="B", visual_description="Visual 2", asset_query="temple"),
    ])
    board = Storyboard(topic="Cholas", shots=[shot(1, existing, "A"), shot(2, None, "stale")])
    issues = scene_mapping_issues(plan, board)
    assert any("Scene 2: storyboard narration differs" in issue for issue in issues)
    assert any("Scene 2: no existing image" in issue for issue in issues)
    assert not any("Scene 1:" in issue for issue in issues)


def test_apply_approved_rejects_stale_narration(tmp_path):
    from historyforgeai.application.services.storyboard import apply_approved, save

    image = tmp_path / "scene.png"
    Image.new("RGB", (10, 10)).save(image)
    plan = ShortPlan(topic="Cholas", title="Temple", narration="Correct", scenes=[
        Scene(index=1, duration_seconds=2, narration="Correct",
              visual_description="Temple", asset_query="temple"),
    ])
    board = Storyboard(topic="Cholas", shots=[
        Shot(scene_index=1, narration="Stale", visual_description="Temple",
             search_query="temple", candidate_image=str(image), status="approved"),
    ])
    plan_path = tmp_path / "scene_plan.json"
    board_path = tmp_path / "storyboard.json"
    plan_path.write_text(plan.model_dump_json())
    save(board_path, board)
    with pytest.raises(ValueError, match="storyboard text differs"):
        apply_approved(plan_path, board_path)
    assert ShortPlan.model_validate_json(plan_path.read_text()).scenes[0].image_path is None
