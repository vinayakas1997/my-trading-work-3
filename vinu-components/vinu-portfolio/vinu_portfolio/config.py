from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

DEFAULT_STRATEGY_API_URL = "http://127.0.0.1:8084"
DEFAULT_RESEARCH_API_URL = "http://127.0.0.1:8087"
DEFAULT_SIMULATOR_API_URL = "http://127.0.0.1:8085"
DEFAULT_AGENT_API_URL = "http://127.0.0.1:8086"
DEFAULT_ANALYSIS_API_URL = "http://127.0.0.1:8083"
DEFAULT_STOCK_API_URL = "http://127.0.0.1:8081"
DEFAULT_DATA_ROOT = Path.cwd() / "data"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8090
DEFAULT_BENCHMARK_SYMBOL = "SPY"
DEFAULT_TAGS_PATH = (
    Path(__file__).resolve().parents[2]
    / "vinu-agent" / "skills" / "strategy-tags" / "tags.yaml"
)

_env_loaded = False


def _ensure_dotenv_loaded(*, force: bool = False) -> None:
    global _env_loaded
    if _env_loaded and not force:
        return
    load_dotenv()
    _env_loaded = True


@dataclass
class PortfolioConfig:
    strategy_api_url: str = DEFAULT_STRATEGY_API_URL
    research_api_url: str = DEFAULT_RESEARCH_API_URL
    simulator_api_url: str = DEFAULT_SIMULATOR_API_URL
    agent_api_url: str = DEFAULT_AGENT_API_URL
    data_root: Path = DEFAULT_DATA_ROOT
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    max_per_strategy_weight: float = 0.3
    max_per_sector_weight: float = 0.4
    risk_free_rate: float = 0.05
    target_volatility: float = 0.15
    drawdown_halt_threshold: float = -0.20
    drawdown_monitor_interval_sec: int = 300
    analysis_api_url: str = DEFAULT_ANALYSIS_API_URL
    stock_api_url: str = DEFAULT_STOCK_API_URL
    benchmark_symbol: str = DEFAULT_BENCHMARK_SYMBOL
    regime_tilt_bound: float = 0.3
    outcome_tilt_bound: float = 0.3
    min_calibration_entries_for_tilt: int = 5
    tags_path: Path = DEFAULT_TAGS_PATH
    game_plan_readiness_threshold: float = 0.5

    @classmethod
    def from_env(cls) -> PortfolioConfig:
        _ensure_dotenv_loaded()
        return cls(
            strategy_api_url=os.getenv("VINU_STRATEGY_API_URL", DEFAULT_STRATEGY_API_URL),
            research_api_url=os.getenv("VINU_RESEARCH_API_URL", DEFAULT_RESEARCH_API_URL),
            simulator_api_url=os.getenv("VINU_SIMULATOR_API_URL", DEFAULT_SIMULATOR_API_URL),
            agent_api_url=os.getenv("VINU_AGENT_API_URL", DEFAULT_AGENT_API_URL),
            data_root=Path(os.getenv("VINU_PORTFOLIO_DATA_ROOT", str(DEFAULT_DATA_ROOT))),
            host=os.getenv("VINU_PORTFOLIO_HOST", DEFAULT_HOST),
            port=int(os.getenv("VINU_PORTFOLIO_PORT", str(DEFAULT_PORT))),
            max_per_strategy_weight=float(os.getenv("VINU_PORTFOLIO_MAX_PER_STRATEGY", "0.3")),
            max_per_sector_weight=float(os.getenv("VINU_PORTFOLIO_MAX_PER_SECTOR", "0.4")),
            drawdown_halt_threshold=float(os.getenv("VINU_PORTFOLIO_DRAWDOWN_HALT", "-0.20")),
            drawdown_monitor_interval_sec=int(os.getenv("VINU_PORTFOLIO_DRAWDOWN_INTERVAL_SEC", "300")),
            analysis_api_url=os.getenv("VINU_CORRELATION_API_URL", DEFAULT_ANALYSIS_API_URL),
            stock_api_url=os.getenv("VINU_STOCK_PRICE_API_URL", DEFAULT_STOCK_API_URL),
            benchmark_symbol=os.getenv("VINU_PORTFOLIO_BENCHMARK_SYMBOL", DEFAULT_BENCHMARK_SYMBOL),
            regime_tilt_bound=float(os.getenv("VINU_PORTFOLIO_REGIME_TILT_BOUND", "0.3")),
            outcome_tilt_bound=float(os.getenv("VINU_PORTFOLIO_OUTCOME_TILT_BOUND", "0.3")),
            min_calibration_entries_for_tilt=int(
                os.getenv("VINU_PORTFOLIO_MIN_CALIBRATION_ENTRIES", "5")
            ),
            tags_path=Path(os.getenv("VINU_PORTFOLIO_TAGS_PATH", str(DEFAULT_TAGS_PATH))),
            game_plan_readiness_threshold=float(
                os.getenv("VINU_PORTFOLIO_GAME_PLAN_READINESS_THRESHOLD", "0.5")
            ),
        )


def load_config() -> PortfolioConfig:
    return PortfolioConfig.from_env()
