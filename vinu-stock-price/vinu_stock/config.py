"""Environment-based configuration for vinu-stock-price."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

DEFAULT_DATA_ROOT = Path.cwd() / "data"
DEFAULT_POLL_INTERVAL_SEC = 60
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8081
DEFAULT_PROVIDER = "polygon"

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
class VinuStockConfig:
    data_root: Path
    meta_db_path: Path
    default_poll_interval_sec: int
    host: str
    port: int
    default_provider: str
    polygon_api_key: str
    alpaca_api_key: str
    alpaca_api_secret: str
    alpaca_data_base_url: str
    shared_watchlist_path: Path | None


def load_config() -> VinuStockConfig:
    _ensure_dotenv_loaded()
    data_root_raw = os.environ.get("VINU_STOCK_DATA_ROOT", "")
    data_root = Path(data_root_raw) if data_root_raw else DEFAULT_DATA_ROOT
    meta_raw = os.environ.get("VINU_STOCK_META_DB_PATH", "")
    meta_db_path = Path(meta_raw) if meta_raw else data_root / "meta.db"
    shared_raw = os.environ.get("VINU_SHARED_WATCHLIST_PATH", "").strip()
    shared_path = Path(shared_raw) if shared_raw else None
    return VinuStockConfig(
        data_root=data_root,
        meta_db_path=meta_db_path,
        default_poll_interval_sec=int(
            os.environ.get("VINU_STOCK_POLL_INTERVAL_SEC", str(DEFAULT_POLL_INTERVAL_SEC))
        ),
        host=os.environ.get("VINU_STOCK_HOST", DEFAULT_HOST),
        port=int(os.environ.get("VINU_STOCK_PORT", str(DEFAULT_PORT))),
        default_provider=os.environ.get("VINU_STOCK_DEFAULT_PROVIDER", DEFAULT_PROVIDER),
        polygon_api_key=os.environ.get("POLYGON_API_KEY", ""),
        alpaca_api_key=os.environ.get("ALPACA_API_KEY", ""),
        alpaca_api_secret=os.environ.get("ALPACA_API_SECRET", ""),
        alpaca_data_base_url=os.environ.get(
            "ALPACA_DATA_BASE_URL", "https://data.alpaca.markets"
        ),
        shared_watchlist_path=shared_path,
    )


def settings_env_defaults() -> dict[str, str]:
    cfg = load_config()
    return {
        "poll_interval_sec": str(cfg.default_poll_interval_sec),
        "default_provider": cfg.default_provider,
        "data_root": str(cfg.data_root),
    }
