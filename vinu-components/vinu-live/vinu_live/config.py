from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

DEFAULT_PORTFOLIO_API_URL = "http://127.0.0.1:8090"
DEFAULT_AGENT_API_URL = "http://127.0.0.1:8086"
DEFAULT_STOCK_PRICE_API_URL = "http://127.0.0.1:8081"
DEFAULT_RESEARCH_API_URL = "http://127.0.0.1:8087"
DEFAULT_INITIAL_ANALYSIS_API_URL = "http://127.0.0.1:8083"
DEFAULT_DATA_ROOT = Path.cwd() / "data"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8091

_env_loaded = False


def _ensure_dotenv_loaded(*, force: bool = False) -> None:
    global _env_loaded
    if _env_loaded and not force:
        return
    load_dotenv()
    _env_loaded = True


@dataclass
class LiveConfig:
    portfolio_api_url: str = DEFAULT_PORTFOLIO_API_URL
    agent_api_url: str = DEFAULT_AGENT_API_URL
    stock_price_api_url: str = DEFAULT_STOCK_PRICE_API_URL
    research_api_url: str = DEFAULT_RESEARCH_API_URL
    initial_analysis_api_url: str = DEFAULT_INITIAL_ANALYSIS_API_URL
    data_root: Path = DEFAULT_DATA_ROOT
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    worker_interval_sec: int = 3600
    max_slippage_pct: float = 0.001
    twap_slices: int = 6
    # "twap" (equal slices) or "vwap" (weighted by historical intraday volume
    # profile, see execution.py::compute_volume_profile) — vwap falls back to
    # equal weighting per-symbol whenever volume data is unavailable, so it's
    # always safe to select even before volume data is verified good.
    execution_style: str = "twap"
    fallback_portfolio_value: float = 1_000_000.0
    trade_plan_worker_interval_sec: int = 300
    feedback_worker_interval_sec: int = 300
    # Shadow evaluation (BENCHING -> ACTIVE promotion) doesn't need to run
    # as often as the trade-plan/feedback loops -- paper-trading Sharpe
    # only moves meaningfully over days, not minutes. 3600s matches the
    # original (pre-Phase-5) worker_interval_sec default rather than
    # inventing a new number; not independently tuned.
    shadow_worker_interval_sec: int = 3600

    @classmethod
    def from_env(cls) -> LiveConfig:
        _ensure_dotenv_loaded()
        return cls(
            portfolio_api_url=os.getenv("VINU_PORTFOLIO_API_URL", DEFAULT_PORTFOLIO_API_URL),
            agent_api_url=os.getenv("VINU_AGENT_API_URL", DEFAULT_AGENT_API_URL),
            stock_price_api_url=os.getenv("VINU_STOCK_PRICE_API_URL", DEFAULT_STOCK_PRICE_API_URL),
            research_api_url=os.getenv("VINU_RESEARCH_API_URL", DEFAULT_RESEARCH_API_URL),
            initial_analysis_api_url=os.getenv(
                "VINU_INITIAL_ANALYSIS_API_URL", DEFAULT_INITIAL_ANALYSIS_API_URL,
            ),
            data_root=Path(os.getenv("VINU_LIVE_DATA_ROOT", str(DEFAULT_DATA_ROOT))),
            host=os.getenv("VINU_LIVE_HOST", DEFAULT_HOST),
            port=int(os.getenv("VINU_LIVE_PORT", str(DEFAULT_PORT))),
            worker_interval_sec=int(os.getenv("VINU_LIVE_INTERVAL", "3600")),
            execution_style=os.getenv("VINU_LIVE_EXECUTION_STYLE", "twap"),
            fallback_portfolio_value=float(os.getenv("VINU_LIVE_FALLBACK_PORTFOLIO_VALUE", "1000000.0")),
            trade_plan_worker_interval_sec=int(
                os.getenv("VINU_LIVE_TRADE_PLAN_INTERVAL", "300"),
            ),
            feedback_worker_interval_sec=int(
                os.getenv("VINU_LIVE_FEEDBACK_INTERVAL", "300"),
            ),
            shadow_worker_interval_sec=int(
                os.getenv("VINU_LIVE_SHADOW_INTERVAL", "3600"),
            ),
        )


def load_config() -> LiveConfig:
    return LiveConfig.from_env()
