from pathlib import Path
import pytest
from PIL import Image

from historyforgeai.bootstrap import build
from historyforgeai.application.services.script_review import approve_script
from historyforgeai.application.services.storyboard import make_storyboard, save
from historyforgeai.application.services.render_job import render_approved_job
from historyforgeai.infrastructure.persistence.characters import CharacterRegistry


class FakeRenderer:
    def __init__(self):
        self.calls = []

    def render(self, plan, job_dir, audio_path, motion="zoom_in"):
        self.calls.append((plan, job_dir, audio_path, motion))
        return str(Path(job_dir) / "short.mp4")


def setup_job(tmp_path):
    pipeline = build("mock", workspace=tmp_path)
    job = pipeline.run("Ashoka", render=False)
    folder = tmp_path / "jobs" / job.id
    from historyforgeai.domain.models import ShortPlan
    plan = ShortPlan.model_validate_json((folder / "scene_plan.json").read_text())
    board = make_storyboard(plan, CharacterRegistry(tmp_path / "characters"))
    image = folder / "approved.png"
    Image.new("RGB", (32, 32), "blue").save(image)
    for shot in board.shots:
        shot.candidate_image = str(image)
    save(folder / "storyboard.json", board)
    approve_script(folder)
    return pipeline, job, folder, board


def test_unapproved_job_does_not_render(tmp_path):
    pipeline, job, folder, board = setup_job(tmp_path)
    renderer = FakeRenderer()
    original = (folder / "scene_plan.json").read_text()
    with pytest.raises(ValueError, match="approved"):
        render_approved_job(job.id, tmp_path, pipeline.repo, renderer)
    assert not renderer.calls
    assert (folder / "scene_plan.json").read_text() == original


def test_approved_job_renders_without_new_job(tmp_path):
    pipeline, job, folder, board = setup_job(tmp_path)
    for shot in board.shots:
        shot.status = "approved"
    save(folder / "storyboard.json", board)
    renderer = FakeRenderer()
    result = render_approved_job(job.id, tmp_path, pipeline.repo, renderer)
    assert result == folder / "short.mp4"
    assert len(renderer.calls) == 1
    assert all(scene.image_path for scene in renderer.calls[0][0].scenes)
    assert pipeline.repo.load(job.id).status.value == "rendered"
    assert len(list((tmp_path / "jobs").glob("*/manifest.json"))) == 1


def test_missing_storyboard_fails_closed(tmp_path):
    pipeline, job, folder, board = setup_job(tmp_path)
    (folder / "storyboard.json").unlink()
    renderer = FakeRenderer()
    with pytest.raises(FileNotFoundError):
        render_approved_job(job.id, tmp_path, pipeline.repo, renderer)
    assert not renderer.calls


class FakeSpeech:
    def __init__(self):
        self.calls = []

    def synthesize(self, text, destination):
        self.calls.append(text)
        Path(destination).write_bytes(b"RIFF" + b"x" * 100)
        return True


def test_review_blocks_audio_until_approval(tmp_path):
    pipeline, job, folder, board = setup_job(tmp_path)
    speech = FakeSpeech()
    renderer = FakeRenderer()
    with pytest.raises(ValueError, match="approved"):
        render_approved_job(job.id, tmp_path, pipeline.repo, renderer, speech=speech)
    assert speech.calls == []
    assert renderer.calls == []


def test_approved_job_generates_audio_before_render(tmp_path):
    pipeline, job, folder, board = setup_job(tmp_path)
    for shot in board.shots:
        shot.status = "approved"
    save(folder / "storyboard.json", board)
    speech = FakeSpeech()
    renderer = FakeRenderer()
    render_approved_job(job.id, tmp_path, pipeline.repo, renderer, speech=speech)
    assert len(speech.calls) == 1
    assert (folder / "narration.wav").is_file()
    assert renderer.calls[0][2] == str(folder / "narration.wav")


def test_missing_script_approval_blocks_render_and_speech(tmp_path):
    pipeline, job, folder, board = setup_job(tmp_path)
    for shot in board.shots:
        shot.status = "approved"
    save(folder / "storyboard.json", board)
    (folder / "script_approval.json").unlink()
    speech = FakeSpeech()
    renderer = FakeRenderer()
    with pytest.raises(ValueError, match="Script is not approved"):
        render_approved_job(job.id, tmp_path, pipeline.repo, renderer, speech=speech)
    assert not speech.calls and not renderer.calls
