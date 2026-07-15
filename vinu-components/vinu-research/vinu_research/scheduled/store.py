from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any

from vinu_research.scheduled.models import ScheduledResearchJob

LOG = logging.getLogger(__name__)

SCHEDULED_ROOT = Path.home() / ".vinu" / "scheduled_research"
JOBS_PATH = SCHEDULED_ROOT / "jobs.json"


class ScheduledResearchJobStore:
    def __init__(self, path: Path | None = None) -> None:
        self._path = path or JOBS_PATH
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def _load(self) -> dict[str, Any]:
        if not self._path.exists():
            return {"schema_version": "0.1", "jobs": {}}
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {"schema_version": "0.1", "jobs": {}}

    def _write(self, data: dict[str, Any]) -> None:
        tmp = None
        try:
            fd, tmp = tempfile.mkstemp(suffix=".tmp", prefix="jobs_", dir=str(self._path.parent))
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, default=str)
                f.flush()
                os.fsync(fd)
            os.replace(tmp, str(self._path))
        except Exception as exc:
            LOG.error("Failed to write jobs to %s: %s", self._path, exc)
            raise
        finally:
            if tmp is not None and os.path.exists(tmp):
                try:
                    os.unlink(tmp)
                except OSError:
                    pass

    def save(self, job: ScheduledResearchJob) -> ScheduledResearchJob:
        data = self._load()
        data["jobs"][job.id] = job.to_dict()
        self._write(data)
        return job

    def get(self, job_id: str) -> ScheduledResearchJob | None:
        data = self._load()
        raw = data["jobs"].get(job_id)
        return ScheduledResearchJob.from_dict(raw) if raw else None

    def list_all(self) -> list[ScheduledResearchJob]:
        data = self._load()
        return [
            ScheduledResearchJob.from_dict(v) for v in data["jobs"].values()
        ]

    def delete(self, job_id: str) -> bool:
        data = self._load()
        if job_id not in data["jobs"]:
            return False
        del data["jobs"][job_id]
        self._write(data)
        return True

    def count(self) -> int:
        return len(self._load()["jobs"])

    def recover_stale_running(self) -> int:
        data = self._load()
        recovered = 0
        for job in data["jobs"].values():
            if job.get("status") == "RUNNING":
                job["status"] = "PENDING"
                recovered += 1
        if recovered:
            self._write(data)
        return recovered
