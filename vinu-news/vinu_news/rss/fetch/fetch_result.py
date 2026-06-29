"""HTTP fetch result dataclasses."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class FetchResult:
    url: str
    status_code: int | None
    body: bytes
    error: str | None
    duration_ms: int


@dataclass
class FeedPollResult:
    feed_id: str
    url: str
    status_code: int | None
    articles: list[dict]
    error: str | None
    duration_ms: int
    article_count: int = field(init=False)

    def __post_init__(self) -> None:
        self.article_count = len(self.articles)

    @property
    def success(self) -> bool:
        return self.error is None and self.article_count > 0
