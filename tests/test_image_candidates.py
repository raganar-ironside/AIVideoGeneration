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
