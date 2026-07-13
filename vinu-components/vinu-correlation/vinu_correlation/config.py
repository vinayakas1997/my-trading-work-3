from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

DEFAULT_DATA_ROOT = Path.cwd() / "data"
DEFAULT_NEWS_API_URL = "http://127.0.0.1:8080"
DEFAULT_STOCK_API_URL = "http://127.0.0.1:8081"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8083
DEFAULT_IMPACT_HIGH_THRESHOLD = 2.0
DEFAULT_IMPACT_MEDIUM_THRESHOLD = 0.5
DEFAULT_DRAWDOWN_MIN_PCT = -3.0
DEFAULT_DRAWDOWN_LOOKBACK_HOURS = 24
DEFAULT_BASELINE_WINDOW_DAYS = 7
DEFAULT_MARKET_HOURS_ONLY = True
DEFAULT_SESSION_BREAK_ON_CLOSE = True
DEFAULT_CACHE_MAXSIZE = 128
DEFAULT_CACHE_TTL_SEC = 300
DEFAULT_COMPUTE_POLL_INTERVAL_SEC = 3600
DEFAULT_COMPACT_THRESHOLD = 50

_ENV_LOADED = False


def _ensure_dotenv_loaded() -> None:
    global _ENV_LOADED
    if _ENV_LOADED:
        return
    package_root = Path(__file__).resolve().parent.parent
    load_dotenv(package_root / ".env")
    load_dotenv()
    _ENV_LOADED = True


@dataclass(frozen=True)
class VinuCorrelationConfig:
    data_root: Path
    news_api_url: str
    stock_api_url: str
    host: str
    port: int
    impact_high_threshold: float
    impact_medium_threshold: float
    drawdown_min_pct: float
    drawdown_lookback_hours: int
    baseline_window_days: int
    market_hours_only: bool
    session_break_on_close: bool
    cache_maxsize: int
    cache_ttl_sec: int
    compute_poll_interval_sec: int
    compact_threshold: int


def load_config() -> VinuCorrelationConfig:
    _ensure_dotenv_loaded()
    data_root_raw = os.environ.get("VINU_CORRELATION_DATA_ROOT", "")
    data_root = Path(data_root_raw) if data_root_raw else DEFAULT_DATA_ROOT
    return VinuCorrelationConfig(
        data_root=data_root,
        news_api_url=os.environ.get("VINU_NEWS_API_URL", DEFAULT_NEWS_API_URL),
        stock_api_url=os.environ.get("VINU_STOCK_API_URL", DEFAULT_STOCK_API_URL),
        host=os.environ.get("VINU_CORRELATION_HOST", DEFAULT_HOST),
        port=int(os.environ.get("VINU_CORRELATION_PORT", str(DEFAULT_PORT))),
        impact_high_threshold=float(
            os.environ.get("VINU_CORRELATION_IMPACT_HIGH_THRESHOLD", str(DEFAULT_IMPACT_HIGH_THRESHOLD))
        ),
        impact_medium_threshold=float(
            os.environ.get("VINU_CORRELATION_IMPACT_MEDIUM_THRESHOLD", str(DEFAULT_IMPACT_MEDIUM_THRESHOLD))
        ),
        drawdown_min_pct=float(
            os.environ.get("VINU_CORRELATION_DRAWDOWN_MIN_PCT", str(DEFAULT_DRAWDOWN_MIN_PCT))
        ),
        drawdown_lookback_hours=int(
            os.environ.get("VINU_CORRELATION_DRAWDOWN_LOOKBACK_HOURS", str(DEFAULT_DRAWDOWN_LOOKBACK_HOURS))
        ),
        baseline_window_days=int(
            os.environ.get("VINU_CORRELATION_BASELINE_WINDOW_DAYS", str(DEFAULT_BASELINE_WINDOW_DAYS))
        ),
        market_hours_only=os.environ.get("VINU_CORRELATION_MARKET_HOURS_ONLY", str(DEFAULT_MARKET_HOURS_ONLY)).lower() == "true",
        session_break_on_close=os.environ.get("VINU_CORRELATION_SESSION_BREAK_ON_CLOSE", str(DEFAULT_SESSION_BREAK_ON_CLOSE)).lower() == "true",
        cache_maxsize=int(os.environ.get("VINU_CORRELATION_CACHE_MAXSIZE", str(DEFAULT_CACHE_MAXSIZE))),
        cache_ttl_sec=int(os.environ.get("VINU_CORRELATION_CACHE_TTL_SEC", str(DEFAULT_CACHE_TTL_SEC))),
        compute_poll_interval_sec=int(
            os.environ.get("VINU_CORRELATION_COMPUTE_POLL_INTERVAL_SEC", str(DEFAULT_COMPUTE_POLL_INTERVAL_SEC))
        ),
        compact_threshold=int(
            os.environ.get("VINU_CORRELATION_COMPACT_THRESHOLD", str(DEFAULT_COMPACT_THRESHOLD))
        ),
    )
