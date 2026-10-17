from pathlib import Path
import pytest
from historyforgeai.bootstrap import build
from historyforgeai.domain.models import ShortPlan, Scene

def test_mock_plan(tmp_path):
    pipeline = build("mock", workspace=tmp_path)
    job = pipeline.run("Ashoka and the Kalinga War", render=False)
    assert job.status.value == "planned"
    plan = ShortPlan.model_validate_json(Path(job.plan_path).read_text())
    assert len(plan.scenes) == 6
    assert sum(s.duration_seconds for s in plan.scenes) == pytest.approx(48)
    assert all(not claim.verified for claim in plan.claims)

def test_bad_scene_sequence():
    with pytest.raises(ValueError):
        ShortPlan(topic="X",title="X",narration="X",scenes=[Scene(index=2,duration_seconds=8,
            narration="Hi",visual_description="x",asset_query="x")])

def test_job_roundtrip(tmp_path):
    pipeline = build("mock", workspace=tmp_path)
    job = pipeline.run("Chola maritime trade", render=False)
    assert pipeline.repo.load(job.id).topic == "Chola maritime trade"
