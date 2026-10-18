"""Generate human-readable, collision-resistant job IDs."""
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path


def new_job_id(topic: str, jobs_root: Path) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", topic.lower()).strip("-")
    slug = slug[:55].rstrip("-") or "untitled"
    date = datetime.now(timezone.utc).strftime("%Y%m%d")
    prefix = f"{date}-{slug}"
    if not (jobs_root / prefix).exists():
        return prefix
    # Preserve the readable topic while avoiding collisions on repeat topics.
    while True:
        candidate = f"{prefix}-{uuid.uuid4().hex[:6]}"
        if not (jobs_root / candidate).exists():
            return candidate
