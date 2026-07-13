"""Load feed definitions from feeds.yaml."""

from __future__ import annotations

import re
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
    only_enabled: bool = True,
    tiers: list[int] | None = None,
) -> list[FeedConfig]:
    """Load feeds; optionally filter by feed id list, enabled state, and tier."""
    feeds_path = path or FEEDS_PATH
    with feeds_path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)

    feeds = [FeedConfig.from_dict(item) for item in data.get("feeds", [])]
    if only_enabled:
        feeds = [f for f in feeds if f.enabled]

    if tiers is not None:
        allowed_tiers = set(tiers)
        feeds = [f for f in feeds if f.tier in allowed_tiers]

    if feed_ids:
        allowed = {fid.strip() for fid in feed_ids}
        feeds = [f for f in feeds if f.id in allowed]

    return feeds


def set_feed_enabled(feed_id: str, enabled: bool, path: Path | None = None) -> FeedConfig:
    """Toggle a feed's enabled flag in feeds.yaml in place, preserving comments/formatting."""
    feeds_path = path or FEEDS_PATH
    text = feeds_path.read_text(encoding="utf-8")

    data = yaml.safe_load(text)
    feeds = [FeedConfig.from_dict(item) for item in data.get("feeds", [])]
    match = next((f for f in feeds if f.id == feed_id), None)
    if match is None:
        raise ValueError(f"Feed not found: {feed_id}")

    pattern = re.compile(
        rf"(-\s*id:\s*{re.escape(feed_id)}\s*\n(?:(?!\s*-\s*id:).)*?\benabled:\s*)(true|false)",
        re.DOTALL,
    )
    new_text, count = pattern.subn(rf"\g<1>{'true' if enabled else 'false'}", text, count=1)
    if count == 0:
        raise ValueError(f"Could not locate 'enabled' field for feed: {feed_id}")

    feeds_path.write_text(new_text, encoding="utf-8")
    match.enabled = enabled
    return match
