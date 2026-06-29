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


def load_config() -> VinuConfig:
    _ensure_dotenv_loaded()
    storage = os.environ.get("VINU_NEWS_STORAGE", "sqlite").lower()
    db_path_raw = os.environ.get("VINU_NEWS_DB_PATH", "")
    db_path = Path(db_path_raw) if db_path_raw else DEFAULT_DB_PATH
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
    )


def settings_env_defaults() -> dict[str, str]:
    """Map VinuConfig fields to vinu_settings keys for first-time DB seed."""
    cfg = load_config()
    return {
        "mode": cfg.default_mode,
        "poll_interval_sec": str(cfg.default_poll_interval_sec),
    }
