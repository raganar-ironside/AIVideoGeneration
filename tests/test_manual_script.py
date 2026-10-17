import json
import pytest
from historyforgeai.application.services.manual_script import import_script
from historyforgeai.infrastructure.persistence.filesystem import FileJobRepository
from historyforgeai.domain.models import ShortPlan


def payload():
    return {
        "topic": "Rajendra Chola", "title": "Chola campaign",
        "duration_seconds": 60, "narration": "The Chola army marched. The campaign continued.",
        "scenes": [
            {"index": 1, "duration_seconds": 25, "narration": "The Chola army marched.",
             "visual_description": "Chola army marching", "asset_query": "Chola army"},
            {"index": 2, "duration_seconds": 35, "narration": "The campaign continued.",
             "visual_description": "Historic map", "asset_query": "Chola empire map"}
        ]
    }


def write(tmp_path, data):
    path = tmp_path / "script.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_import_creates_planned_job_and_compatible_plan(tmp_path):
    repo = FileJobRepository(tmp_path / "workspace" / "jobs")
    job = import_script(write(tmp_path, payload()), tmp_path / "workspace", repo)
    assert job.status.value == "planned"
    assert repo.load(job.id).plan_path == job.plan_path
    plan = ShortPlan.model_validate_json((tmp_path / "workspace" / "jobs" / job.id / "scene_plan.json").read_text())
    assert len(plan.scenes) == 2
    assert plan.narration == payload()["narration"]


@pytest.mark.parametrize("change", ["duration", "narration", "indexes"])
def test_invalid_import_creates_no_job(tmp_path, change):
    data = payload()
    if change == "duration":
        data["duration_seconds"] = 59
    elif change == "narration":
        data["scenes"][1]["narration"] = "Different narration."
    else:
        data["scenes"][1]["index"] = 3
    repo = FileJobRepository(tmp_path / "workspace" / "jobs")
    with pytest.raises(ValueError):
        import_script(write(tmp_path, data), tmp_path / "workspace", repo)
    assert not list(repo.root.glob("*/manifest.json"))
