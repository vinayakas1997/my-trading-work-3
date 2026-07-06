from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8084
DEFAULT_DATA_ROOT = Path.cwd() / "data"
DEFAULT_STRATEGIES_DIR = Path.cwd() / "strategies"
DEFAULT_FEATURES_API_URL = "http://127.0.0.1:8082"
DEFAULT_CORRELATION_API_URL = "http://127.0.0.1:8083"
DEFAULT_MAX_WEIGHT = 0.25
DEFAULT_CASH_FLOOR = 0.10
DEFAULT_REBALANCE_FREQ = "daily"

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
class VinuStrategyConfig:
    host: str
    port: int
    data_root: Path
    strategies_dir: Path
    features_api_url: str
    correlation_api_url: str
    max_weight: float
    cash_floor: float
    rebalance_freq: str
    shared_watchlist_path: Path | None


def load_config() -> VinuStrategyConfig:
    _ensure_dotenv_loaded()
    data_root_raw = os.environ.get("VINU_STRATEGY_DATA_ROOT", "")
    data_root = Path(data_root_raw) if data_root_raw else DEFAULT_DATA_ROOT
    strategies_dir_raw = os.environ.get("VINU_STRATEGY_STRATEGIES_DIR", "")
    strategies_dir = Path(strategies_dir_raw) if strategies_dir_raw else DEFAULT_STRATEGIES_DIR
    watch_raw = os.environ.get("VINU_SHARED_WATCHLIST_PATH", "")
    watch_path = Path(watch_raw) if watch_raw else None
    return VinuStrategyConfig(
        host=os.environ.get("VINU_STRATEGY_HOST", DEFAULT_HOST),
        port=int(os.environ.get("VINU_STRATEGY_PORT", str(DEFAULT_PORT))),
        data_root=data_root,
        strategies_dir=strategies_dir,
        features_api_url=os.environ.get("VINU_FEATURES_API_URL", DEFAULT_FEATURES_API_URL),
        correlation_api_url=os.environ.get("VINU_CORRELATION_API_URL", DEFAULT_CORRELATION_API_URL),
        max_weight=float(os.environ.get("VINU_STRATEGY_MAX_WEIGHT", str(DEFAULT_MAX_WEIGHT))),
        cash_floor=float(os.environ.get("VINU_STRATEGY_CASH_FLOOR", str(DEFAULT_CASH_FLOOR))),
        rebalance_freq=os.environ.get("VINU_STRATEGY_REBALANCE_FREQ", DEFAULT_REBALANCE_FREQ),
        shared_watchlist_path=watch_path,
    )
