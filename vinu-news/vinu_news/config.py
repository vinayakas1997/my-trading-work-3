"""Environment-based configuration for vinu-news."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

DEFAULT_DB_PATH = Path.cwd() / "data" / "news.db"
DEFAULT_MODE = "ticker"
DEFAULT_POLL_INTERVAL_SEC = 600
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8080
DEFAULT_STOCK_API_URL = "http://127.0.0.1:8081"
DEFAULT_LLM_BASE_URL = "http://127.0.0.1:11434/v1"
DEFAULT_LLM_MODEL = "llama3.2"
DEFAULT_LLM_TTL_SEC = 86400

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
class VinuConfig:
    storage: str
    db_path: Path
    database_url: str | None
    default_mode: str
    default_poll_interval_sec: int
    host: str
    port: int
    shared_watchlist_path: Path | None
    stock_api_url: str
    llm_base_url: str
    llm_model: str
    llm_api_key: str | None
    llm_ttl_sec: int
    fmp_api_key: str


def load_config() -> VinuConfig:
    _ensure_dotenv_loaded()
    storage = os.environ.get("VINU_NEWS_STORAGE", "sqlite").lower()
    db_path_raw = os.environ.get("VINU_NEWS_DB_PATH", "")
    db_path = Path(db_path_raw) if db_path_raw else DEFAULT_DB_PATH
    shared_raw = os.environ.get("VINU_SHARED_WATCHLIST_PATH", "").strip()
    shared_path = Path(shared_raw) if shared_raw else None
    return VinuConfig(
        storage=storage,
        db_path=db_path,
        database_url=os.environ.get("VINU_NEWS_DATABASE_URL"),
        default_mode=os.environ.get("VINU_NEWS_MODE", DEFAULT_MODE).lower(),
        default_poll_interval_sec=int(
            os.environ.get("VINU_NEWS_POLL_INTERVAL_SEC", str(DEFAULT_POLL_INTERVAL_SEC))
        ),
        host=os.environ.get("VINU_NEWS_HOST", DEFAULT_HOST),
        port=int(os.environ.get("VINU_NEWS_PORT", str(DEFAULT_PORT))),
        shared_watchlist_path=shared_path,
        stock_api_url=os.environ.get("VINU_STOCK_API_URL", DEFAULT_STOCK_API_URL),
        llm_base_url=os.environ.get("VINU_LLM_BASE_URL", DEFAULT_LLM_BASE_URL),
        llm_model=os.environ.get("VINU_LLM_MODEL", DEFAULT_LLM_MODEL),
        llm_api_key=os.environ.get("VINU_LLM_API_KEY") or None,
        llm_ttl_sec=int(os.environ.get("VINU_LLM_TTL_SEC", str(DEFAULT_LLM_TTL_SEC))),
        fmp_api_key=os.environ.get("FMP_API_KEY", ""),
    )


def settings_env_defaults() -> dict[str, str]:
    """Map VinuConfig fields to vinu_settings keys for first-time DB seed."""
    cfg = load_config()
    return {
        "mode": cfg.default_mode,
        "poll_interval_sec": str(cfg.default_poll_interval_sec),
    }
