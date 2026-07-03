"""Ingestion settings matching Fincept Step 1 resilience defaults."""

import os

from vinu_news.config import load_config

REQUEST_TIMEOUT_SEC = 4
USER_AGENT = "FinceptTerminal-Research/1.0 (+local-news-ingestion)"
HTML_CLOAK_PREFIX_LEN = 20
MIN_BODY_BYTES = 50
DEFAULT_POLL_INTERVAL_SEC = 900


def get_max_workers() -> int:
    """Return the configured max parallel feed workers."""
    try:
        return load_config().max_workers
    except Exception:
        return 8
