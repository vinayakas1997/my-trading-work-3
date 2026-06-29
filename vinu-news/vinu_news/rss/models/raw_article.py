"""Raw article model for pipeline handoff."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class RawArticle:
    headline: str
    summary: str
    link: str
    pubDate: str
    source: str
    region: str
    tier: int
    category: str = "MARKETS"

    def to_pipeline_dict(self) -> dict[str, Any]:
        return asdict(self)
