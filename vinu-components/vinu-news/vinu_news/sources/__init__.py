"""News sources: health, switches and the read-out (layer 1 of the news plan)."""
from vinu_news.sources.health import (  # noqa: F401
    BACKOFF_SECONDS,
    KIND_API,
    KIND_RSS,
    SourceHealth,
    auto_off_after,
    classify_error,
    migrate,
)
