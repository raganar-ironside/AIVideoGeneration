"""Import a user-authored script into the existing job/storyboard workflow."""
import json
import uuid
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator
from historyforgeai.domain.models import Job, JobStatus, Scene, ShortPlan


class ManualScript(BaseModel):
    model_config = ConfigDict(extra="forbid")
    topic: str = Field(min_length=1)
    title: str = Field(min_length=1)
    duration_seconds: float = Field(gt=0)
    narration: str = Field(min_length=1)
    scenes: list[Scene] = Field(min_length=1)

    @model_validator(mode="after")
    def check_consistency(self):
        total = sum(scene.duration_seconds for scene in self.scenes)
        if abs(total - self.duration_seconds) > 0.01:
            raise ValueError(f"Scene durations total {total:g}s, expected {self.duration_seconds:g}s")
        combined = " ".join(scene.narration.strip() for scene in self.scenes)
        normalize = lambda s: " ".join(s.split())
        if normalize(combined) != normalize(self.narration):
            raise ValueError("Scene narrations must concatenate to the full narration in order")
        return self


def import_script(source: Path, workspace: Path, repository) -> Job:
    """Validate first; create a new planned job only for valid input."""
    data = json.loads(Path(source).read_text(encoding="utf-8"))
    manual = ManualScript.model_validate(data)
    plan = ShortPlan(topic=manual.topic, title=manual.title,
                     narration=manual.narration, scenes=manual.scenes)
    job = Job(id=uuid.uuid4().hex[:12], topic=plan.topic, status=JobStatus.PLANNED)
    folder = Path(workspace) / "jobs" / job.id
    folder.mkdir(parents=True, exist_ok=False)
    plan_path = folder / "scene_plan.json"
    plan_path.write_text(plan.model_dump_json(indent=2), encoding="utf-8")
    job.plan_path = str(plan_path)
    repository.save(job)
    return job
