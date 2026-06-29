"""Ingestion settings matching Fincept Step 1 resilience defaults."""

REQUEST_TIMEOUT_SEC = 4
MAX_WORKERS = 8
USER_AGENT = "FinceptTerminal-Research/1.0 (+local-news-ingestion)"
HTML_CLOAK_PREFIX_LEN = 20
MIN_BODY_BYTES = 50
DEFAULT_POLL_INTERVAL_SEC = 900
