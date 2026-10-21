from pathlib import Path
from unittest.mock import patch

import pytest
from PIL import Image

from historyforgeai.application.services.image_candidates import create_candidate
from historyforgeai.application.services.storyboard import Storyboard, Shot, save, load


@pytest.fixture
def job_dir(tmp_path):
    folder = tmp_path / "jobs" / "testjob"
    folder.mkdir(parents=True)
    save(folder / "storyboard.json", Storyboard(topic="Test", shots=[
        Shot(scene_index=1, narration="Narration", visual_description="Ancient temple",
             search_query="temple", status="approved")
    ]))
    return folder


def test_manual_image_copies_and_resets_approval(job_dir, tmp_path):
    source = tmp_path / "image.png"
    Image.new("RGB", (64, 64)).save(source)
    destination = create_candidate(job_dir, 1, "manual", source)
    assert destination.is_file()
    assert destination.suffix == ".jpg"
    shot = load(job_dir / "storyboard.json").shots[0]
    assert shot.candidate_image == str(destination)
    assert shot.status == "pending_review"


def test_missing_manual_file_does_not_change_review(job_dir):
    with pytest.raises(FileNotFoundError):
        create_candidate(job_dir, 1, "manual", Path("/does/not/exist.png"))
    assert load(job_dir / "storyboard.json").shots[0].status == "approved"


def test_paid_guard_prevents_network(job_dir):
    with patch("historyforgeai.application.services.image_candidates.requests.post") as post:
        with pytest.raises(ValueError, match="allow-paid"):
            create_candidate(job_dir, 1, "openai")
        post.assert_not_called()


def test_unknown_scene(job_dir):
    with pytest.raises(ValueError, match="not found"):
        create_candidate(job_dir, 3, "manual")


def test_uploaded_image_is_imported_and_requires_review(job_dir):
    from io import BytesIO
    from historyforgeai.application.services.image_candidates import create_uploaded_candidate

    image = BytesIO()
    Image.new("RGB", (48, 80), "red").save(image, format="PNG")
    destination = create_uploaded_candidate(job_dir, 1, image.getvalue())
    assert destination.is_file()
    with Image.open(destination) as result:
        assert result.format == "JPEG"
        assert result.size == (48, 80)
    shot = load(job_dir / "storyboard.json").shots[0]
    assert shot.candidate_image == str(destination)
    assert shot.status == "pending_review"
    assert list((job_dir / "assets").glob("*.upload")) == []


def test_invalid_uploaded_bytes_preserve_storyboard(job_dir):
    from historyforgeai.application.services.image_candidates import create_uploaded_candidate

    with pytest.raises((OSError, ValueError)):
        create_uploaded_candidate(job_dir, 1, b"not an image")
    assert load(job_dir / "storyboard.json").shots[0].status == "approved"
    assert list((job_dir / "assets").glob("*.upload")) == []


def test_oversized_upload_is_rejected(job_dir):
    from historyforgeai.application.services.image_candidates import create_uploaded_candidate

    with pytest.raises(ValueError, match="20 MB"):
        create_uploaded_candidate(job_dir, 1, b"x" * (20 * 1024 * 1024 + 1))


def test_upload_to_one_scene_preserves_other_scene_images_and_reviews(job_dir):
    from io import BytesIO
    from historyforgeai.application.services.image_candidates import create_uploaded_candidate

    existing = job_dir / "previous_scene.jpg"
    Image.new("RGB", (30, 30), "blue").save(existing)
    board_path = job_dir / "storyboard.json"
    board = load(board_path)
    board.shots.extend([
        Shot(scene_index=2, narration="Second", visual_description="Another view",
             search_query="view", candidate_image=str(existing), status="approved",
             source_url="https://example.org/image", license="CC BY", attribution="Author"),
        Shot(scene_index=3, narration="Third", visual_description="Other view",
             search_query="other", status="rejected"),
    ])
    save(board_path, board)
    previous_second = board.shots[1].model_dump()
    previous_third = board.shots[2].model_dump()

    image = BytesIO()
    Image.new("RGB", (48, 80), "red").save(image, format="PNG")
    uploaded_path = create_uploaded_candidate(job_dir, 1, image.getvalue())

    result = load(board_path)
    assert result.shots[0].candidate_image == str(uploaded_path)
    assert result.shots[0].status == "pending_review"
    assert result.shots[1].model_dump() == previous_second
    assert result.shots[2].model_dump() == previous_third
    assert existing.is_file()


def test_sequential_scene_uploads_preserve_earlier_uploads(job_dir):
    from io import BytesIO
    from historyforgeai.application.services.image_candidates import create_uploaded_candidate

    board_path = job_dir / "storyboard.json"
    board = load(board_path)
    board.shots.extend([
        Shot(scene_index=index, narration=f"Scene {index}",
             visual_description="Temple", search_query="temple")
        for index in range(2, 9)
    ])
    save(board_path, board)
    destinations = {}
    for index in range(1, 9):
        image = BytesIO()
        Image.new("RGB", (32 + index, 32), (index * 20, 0, 0)).save(image, format="PNG")
        destinations[index] = str(create_uploaded_candidate(job_dir, index, image.getvalue()))
        current = load(board_path)
        for previous_index in range(1, index + 1):
            assert current.shots[previous_index - 1].candidate_image == destinations[previous_index]
            assert Path(destinations[previous_index]).is_file()
