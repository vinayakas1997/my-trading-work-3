from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8085
DEFAULT_DATA_ROOT = Path.cwd() / "data"
DEFAULT_INITIAL_CAPITAL = 1_000_000.0
DEFAULT_TRANSACTION_COST_PCT = 0.001
DEFAULT_SLIPPAGE_PCT = 0.0005
DEFAULT_BENCHMARK_TICKERS = ("SPY", "QQQ")
DEFAULT_ALLOW_SHORT = True
DEFAULT_STRATEGY_API_URL = "http://127.0.0.1:8084"
DEFAULT_STOCK_API_URL = "http://127.0.0.1:8081"
DEFAULT_FEATURES_API_URL = "http://127.0.0.1:8082"
DEFAULT_DEVIATION_THRESHOLD = 0.05

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
class VinuSimulatorConfig:
    host: str
    port: int
    data_root: Path
    initial_capital: float
    transaction_cost_pct: float
    slippage_pct: float
    benchmark_tickers: tuple[str, ...]
    allow_short: bool
    strategy_api_url: str
    stock_api_url: str
    features_api_url: str
    deviation_threshold: float


def load_config() -> VinuSimulatorConfig:
    _ensure_dotenv_loaded()
    data_root_raw = os.environ.get("VINU_SIMULATOR_DATA_ROOT", "")
    data_root = Path(data_root_raw) if data_root_raw else DEFAULT_DATA_ROOT
    bm_raw = os.environ.get("VINU_SIMULATOR_BENCHMARK_TICKERS", "")
    bm = tuple(t.strip() for t in bm_raw.split(",")) if bm_raw else DEFAULT_BENCHMARK_TICKERS
    return VinuSimulatorConfig(
        host=os.environ.get("VINU_SIMULATOR_HOST", DEFAULT_HOST),
        port=int(os.environ.get("VINU_SIMULATOR_PORT", str(DEFAULT_PORT))),
        data_root=data_root,
        initial_capital=float(os.environ.get("VINU_SIMULATOR_INITIAL_CAPITAL", str(DEFAULT_INITIAL_CAPITAL))),
        transaction_cost_pct=float(os.environ.get("VINU_SIMULATOR_TRANSACTION_COST_PCT", str(DEFAULT_TRANSACTION_COST_PCT))),
        slippage_pct=float(os.environ.get("VINU_SIMULATOR_SLIPPAGE_PCT", str(DEFAULT_SLIPPAGE_PCT))),
        benchmark_tickers=bm,
        allow_short=os.environ.get("VINU_SIMULATOR_ALLOW_SHORT", str(DEFAULT_ALLOW_SHORT)).lower() == "true",
        strategy_api_url=os.environ.get("VINU_STRATEGY_API_URL", DEFAULT_STRATEGY_API_URL),
        stock_api_url=os.environ.get("VINU_STOCK_API_URL", DEFAULT_STOCK_API_URL),
        features_api_url=os.environ.get("VINU_FEATURES_API_URL", DEFAULT_FEATURES_API_URL),
        deviation_threshold=float(os.environ.get("VINU_SIMULATOR_DEVIATION_THRESHOLD", str(DEFAULT_DEVIATION_THRESHOLD))),
    )
