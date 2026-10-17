from enum import Enum
from pydantic import BaseModel, Field, model_validator

class JobStatus(str, Enum):
    CREATED = "created"
    PLANNED = "planned"
    ASSETS_READY = "assets_ready"
    RENDERED = "rendered"
    FAILED = "failed"

class Claim(BaseModel):
    statement: str
    source_urls: list[str] = Field(default_factory=list)
    verified: bool = False

class Scene(BaseModel):
    index: int = Field(ge=1)
    duration_seconds: float = Field(gt=0)
    narration: str
    visual_description: str
    asset_query: str
    visual_type: str = "historical_artifact"
    character_ids: list[str] = Field(default_factory=list)
    image_path: str | None = None
    asset_source_url: str | None = None
    asset_license: str | None = None
    attribution: str | None = None

class ShortPlan(BaseModel):
    topic: str
    title: str
    narration: str
    claims: list[Claim] = Field(default_factory=list)
    scenes: list[Scene] = Field(min_length=1)
    disclaimer: str = "AI reconstructions, if any, are illustrative."

    @model_validator(mode="after")
    def validate_scenes(self):
        if [s.index for s in self.scenes] != list(range(1, len(self.scenes) + 1)):
            raise ValueError("Scene indexes must be sequential starting at 1")
        return self

class Job(BaseModel):
    id: str
    topic: str
    status: JobStatus = JobStatus.CREATED
    plan_path: str | None = None
    video_path: str | None = None
    errors: list[str] = Field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost_usd: float = 0.0
    approved: bool = False
