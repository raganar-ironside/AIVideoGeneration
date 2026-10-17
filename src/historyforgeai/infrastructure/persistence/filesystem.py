from pathlib import Path
from historyforgeai.domain.models import Job

class FileJobRepository:
    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, job: Job) -> None:
        folder = self.root / job.id
        folder.mkdir(parents=True, exist_ok=True)
        dest = folder / "manifest.json"
        tmp = folder / "manifest.json.tmp"
        tmp.write_text(job.model_dump_json(indent=2), encoding="utf-8")
        tmp.replace(dest)

    def load(self, job_id: str) -> Job:
        return Job.model_validate_json((self.root / job_id / "manifest.json").read_text(encoding="utf-8"))
