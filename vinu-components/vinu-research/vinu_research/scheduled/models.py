from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class ScheduledResearchJob:
    id: str
    prompt: str
    schedule: str
    next_run_at: str = ""
    status: str = "PENDING"
    interval_ms: int = 0
    run_count: int = 0
    last_error: str = ""
    created_at: str = ""
    updated_at: str = ""
    # The last completed run's human-readable summary (ResearchRunRecord's
    # summary_text) — dispatch() used to call run_research() and discard its
    # entire return value, so a scheduled run's outcome was unrecoverable
    # without separately guessing which /research/runs row it produced.
    last_run_id: int | None = None
    last_summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "prompt": self.prompt,
            "schedule": self.schedule,
            "next_run_at": self.next_run_at,
            "status": self.status,
            "interval_ms": self.interval_ms,
            "run_count": self.run_count,
            "last_error": self.last_error,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "last_run_id": self.last_run_id,
            "last_summary": self.last_summary,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ScheduledResearchJob:
        return cls(
            id=d["id"],
            prompt=d.get("prompt", ""),
            schedule=d.get("schedule", ""),
            next_run_at=d.get("next_run_at", ""),
            status=d.get("status", "PENDING"),
            interval_ms=int(d.get("interval_ms", 0)),
            run_count=int(d.get("run_count", 0)),
            last_error=d.get("last_error", ""),
            created_at=d.get("created_at", ""),
            updated_at=d.get("updated_at", ""),
            last_run_id=d.get("last_run_id"),
            last_summary=d.get("last_summary", ""),
        )

    @classmethod
    def create(cls, prompt: str, schedule: str, interval_ms: int = 0) -> ScheduledResearchJob:
        import hashlib
        now = datetime.now(timezone.utc).isoformat()
        raw = f"{prompt}:{schedule}:{now}"
        job_id = f"job_{hashlib.sha256(raw.encode()).hexdigest()[:12]}"
        return cls(
            id=job_id,
            prompt=prompt,
            schedule=schedule,
            interval_ms=interval_ms,
            next_run_at=now,
            created_at=now,
            updated_at=now,
        )
