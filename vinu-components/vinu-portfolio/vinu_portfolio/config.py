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
    # Stage C (C11): "hrp" (default as of 2026-09-11 — Hierarchical Risk
    # Parity, correlation-aware, inversion-free, degrades gracefully on an
    # ill-conditioned matrix; falls back to "inverse_vol" automatically
    # when there isn't enough return history to cluster, so this default
    # change never removes coverage, only adds correlation-awareness where
    # there's enough history for it) or "inverse_vol" (1/vol,
    # correlation-blind, always well-defined — the old default, still
    # available as an explicit opt-out). Env: VINU_PORTFOLIO_ALLOCATION_MODE.
    allocation_mode: str = "hrp"
    # Stage C (C12): post-construction rescaling — cap the *combined* target
    # weight of any cluster of names whose pairwise correlation is >=
    # cluster_corr_threshold. Defaults on as of 2026-09-11 (0.6 combined
    # weight cap at a 0.8 correlation threshold — five names that all move
    # together can't collectively exceed 60% of the book without an
    # explicit override); 1.0 disables the cap entirely. Env:
    # VINU_PORTFOLIO_MAX_CORRELATED_CLUSTER_WEIGHT / _CLUSTER_CORR_THRESHOLD.
    max_correlated_cluster_weight: float = 0.6
    cluster_corr_threshold: float = 0.8
    risk_free_rate: float = 0.05
    target_volatility: float = 0.15
    drawdown_halt_threshold: float = -0.20
    drawdown_monitor_interval_sec: int = 300
    # Stage A (A16): absolute session-loss halt, independent of the
    # drawdown-from-peak breaker above. 0.0 = disabled (default).
    abs_loss_halt_threshold: float = 0.0
    analysis_api_url: str = DEFAULT_ANALYSIS_API_URL
    stock_api_url: str = DEFAULT_STOCK_API_URL
    benchmark_symbol: str = DEFAULT_BENCHMARK_SYMBOL
    regime_tilt_bound: float = 0.3
    outcome_tilt_bound: float = 0.3
    # Stage 2 (how-to-make-it-live.md #34): a strategy that barely cleared
    # the promotion bar (deflated Sharpe just above threshold) used to get
    # identical allocation weight to one that cleared it comfortably --
    # the promotion decision was binary, and nothing downstream carried the
    # margin forward. confidence_tilt_bound mirrors regime/outcome_tilt_bound's
    # own +-30% shape; promotion_deflated_sharpe_threshold must track
    # vinu-research's own ResearchConfig.promotion_deflated_sharpe_threshold
    # (both default to 0.95) -- duplicated across the service boundary the
    # same way this session's other cross-service fixes were, since
    # vinu-portfolio has no dependency on vinu-research's config module.
    confidence_tilt_bound: float = 0.3
    promotion_deflated_sharpe_threshold: float = 0.95
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
            allocation_mode=os.getenv("VINU_PORTFOLIO_ALLOCATION_MODE", "hrp"),
            max_correlated_cluster_weight=float(os.getenv("VINU_PORTFOLIO_MAX_CORRELATED_CLUSTER_WEIGHT", "0.6")),
            cluster_corr_threshold=float(os.getenv("VINU_PORTFOLIO_CLUSTER_CORR_THRESHOLD", "0.8")),
            drawdown_halt_threshold=float(os.getenv("VINU_PORTFOLIO_DRAWDOWN_HALT", "-0.20")),
            drawdown_monitor_interval_sec=int(os.getenv("VINU_PORTFOLIO_DRAWDOWN_INTERVAL_SEC", "300")),
            abs_loss_halt_threshold=float(os.getenv("VINU_PORTFOLIO_ABS_LOSS_HALT", "0.0")),
            analysis_api_url=os.getenv("VINU_CORRELATION_API_URL", DEFAULT_ANALYSIS_API_URL),
            stock_api_url=os.getenv("VINU_STOCK_PRICE_API_URL", DEFAULT_STOCK_API_URL),
            benchmark_symbol=os.getenv("VINU_PORTFOLIO_BENCHMARK_SYMBOL", DEFAULT_BENCHMARK_SYMBOL),
            regime_tilt_bound=float(os.getenv("VINU_PORTFOLIO_REGIME_TILT_BOUND", "0.3")),
            outcome_tilt_bound=float(os.getenv("VINU_PORTFOLIO_OUTCOME_TILT_BOUND", "0.3")),
            confidence_tilt_bound=float(os.getenv("VINU_PORTFOLIO_CONFIDENCE_TILT_BOUND", "0.3")),
            promotion_deflated_sharpe_threshold=float(
                os.getenv("VINU_PORTFOLIO_PROMOTION_DSR_THRESHOLD", "0.95")
            ),
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
