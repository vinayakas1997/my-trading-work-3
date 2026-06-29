"""Load feed definitions from feeds.yaml."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

FEEDS_PATH = Path(__file__).resolve().parent / "feeds.yaml"


@dataclass
class FeedConfig:
    id: str
    url: str
    source: str
    region: str
    tier: int
    category: str
    enabled: bool = True

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FeedConfig:
        return cls(
            id=data["id"],
            url=data["url"],
            source=data["source"],
            region=data["region"],
            tier=int(data["tier"]),
            category=data.get("category", "MARKETS"),
            enabled=bool(data.get("enabled", True)),
        )


def load_feeds(
    path: Path | None = None,
    feed_ids: list[str] | None = None,
) -> list[FeedConfig]:
    """Load enabled feeds; optionally filter by feed id list."""
    feeds_path = path or FEEDS_PATH
    with feeds_path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)

    feeds = [FeedConfig.from_dict(item) for item in data.get("feeds", [])]
    feeds = [f for f in feeds if f.enabled]

    if feed_ids:
        allowed = {fid.strip() for fid in feed_ids}
        feeds = [f for f in feeds if f.id in allowed]

    return feeds
