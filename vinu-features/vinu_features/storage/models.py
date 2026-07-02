"""Feature request domain models."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

STATUS_PENDING = "pending"
STATUS_RUNNING = "running"
STATUS_DONE = "done"
STATUS_FAILED = "failed"
STATUS_DELETED = "deleted"

VALID_STATUSES = frozenset(
    {STATUS_PENDING, STATUS_RUNNING, STATUS_DONE, STATUS_FAILED, STATUS_DELETED}
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def slugify_title(title: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", title.strip().lower()).strip("_")
    return slug or "run"


@dataclass
class FeatureRequest:
    id: int | None
    title: str
    slug: str
    symbols: list[str]
    from_ts: int
    to_ts: int
    interval: str
    preset: str | None
    features: list[str]
    conditions: str | None
    status: str
    file_path: str | None
    error_message: str | None
    request_hash: str
    created_at: str
    updated_at: str
    row_count: int = 0
    ml_model: str | None = None
    ml_label: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "slug": self.slug,
            "symbols": self.symbols,
            "from_ts": self.from_ts,
            "to_ts": self.to_ts,
            "interval": self.interval,
            "preset": self.preset,
            "features": self.features,
            "conditions": self.conditions,
            "status": self.status,
            "file_path": self.file_path,
            "error_message": self.error_message,
            "request_hash": self.request_hash,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "row_count": self.row_count,
            "ml_model": self.ml_model,
            "ml_label": self.ml_label,
        }

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> FeatureRequest:
        symbols = row["symbols"]
        features = row["features"]
        if isinstance(symbols, str):
            symbols = json.loads(symbols)
        if isinstance(features, str):
            features = json.loads(features)
        return cls(
            id=row["id"],
            title=row["title"],
            slug=row["slug"],
            symbols=list(symbols),
            from_ts=int(row["from_ts"]),
            to_ts=int(row["to_ts"]),
            interval=row["interval"],
            preset=row.get("preset"),
            features=list(features),
            conditions=row.get("conditions"),
            status=row["status"],
            file_path=row.get("file_path"),
            error_message=row.get("error_message"),
            request_hash=row["request_hash"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            row_count=int(row.get("row_count") or 0),
            ml_model=row.get("ml_model"),
            ml_label=row.get("ml_label"),
        )


@dataclass
class SubmitRequest:
    title: str
    symbols: list[str]
    from_ts: int
    to_ts: int
    interval: str = "1d"
    preset: str | None = None
    features: list[str] = field(default_factory=list)
    conditions: str | None = None
    ml_model: str | None = None
    ml_label: str | None = None
