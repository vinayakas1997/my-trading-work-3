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
DEFAULT_LIVE_API_URL = "http://127.0.0.1:8091"
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
    # The YAML registry strategies were never research-validated; by default only ACTIVE research artifacts get capital.
    include_yaml_strategies: bool = False
    # Capital allocator (capital_allocator.py), used only when VINU_REAL_CAPITAL is set (see vinu_infra.account_mode).
    live_api_url: str = DEFAULT_LIVE_API_URL
    capital_kelly_scale: float = 0.25        # a quarter of full Kelly: the edge estimates are noisy
    capital_max_position_pct: float = 0.25   # no position above this share of the real capital (matches the mandate)
    capital_min_history: int = 20            # periods of return history a strategy needs before it can be funded
    capital_fractional_shares: bool = False  # whole shares: the scheduler rounds down, and extended hours cannot do fractions
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
    # Fraction of account equity held back from sizing entirely -- a
    # restart/safety fund ordinary position sizing cannot touch. 0.0
    # (default) is a no-op: every existing deployment sizes against full
    # equity exactly as before until this is explicitly set. Env:
    # VINU_PORTFOLIO_RESERVE_FRACTION.
    reserve_fraction: float = 0.0
    # Shared ticker-profile writes (compute_daily_allocation's per-symbol
    # target weight): None (default) is a no-op -- ships inert, no write
    # ever attempted. Env: VINU_SHARED_ROOT.
    shared_root: Path | None = None
    # system-wide-audit-and-design item #4 (senior-quant "gradual capital
    # scaling" expectation): a system-wide MaturityAssessment
    # (cold_start/paper_only/early_live/mature -- vinu-research's own
    # maturity_assessor.py, already wired into trade-plan-authoring's LLM
    # prompt) previously never touched capital sizing at all. False
    # (default) is a no-op -- every existing deployment sizes exactly as
    # before until this is explicitly enabled, same opt-in posture
    # vinu-research's own `maturity_tier_enabled` already uses for the
    # prompt-context wiring. Deliberately fails OPEN (multiplier 1.0, no
    # restriction) if the maturity assessment is unavailable for any
    # reason -- unlike a missing risk signal that should conservatively
    # restrict, an outage in this brand-new bridge must not be able to
    # silently zero out deployable capital system-wide; every other tilt
    # in this same pipeline already fails open the same way for an
    # analogous reason. Env: VINU_PORTFOLIO_MATURITY_CAPITAL_GATING_ENABLED.
    maturity_capital_gating_enabled: bool = False
    # Multipliers applied to the WHOLE portfolio's deployable_equity (the
    # same mechanism drawdown_mult already scales, not a per-strategy
    # tilt -- MaturityAssessment is a single system-wide value, computed
    # across every strategy's own trade/paper history, not one per
    # strategy). Reasonable starting points, not a statistically derived
    # ramp -- same "revisit once real data exists" caveat trade_score_gate.py's
    # own scoring weights already carry. `mature` is intentionally not
    # configurable here: 1.0 there just means "no restriction," not a
    # separate knob to tune. Env: VINU_PORTFOLIO_MATURITY_MULT_COLD_START /
    # _PAPER_ONLY / _EARLY_LIVE.
    maturity_capital_multiplier_cold_start: float = 0.1
    maturity_capital_multiplier_paper_only: float = 0.25
    maturity_capital_multiplier_early_live: float = 0.5

    @classmethod
    def from_env(cls) -> PortfolioConfig:
        _ensure_dotenv_loaded()
        return cls(
            strategy_api_url=os.getenv("VINU_STRATEGY_API_URL", DEFAULT_STRATEGY_API_URL),
            research_api_url=os.getenv("VINU_RESEARCH_API_URL", DEFAULT_RESEARCH_API_URL),
            simulator_api_url=os.getenv("VINU_SIMULATOR_API_URL", DEFAULT_SIMULATOR_API_URL),
            agent_api_url=os.getenv("VINU_AGENT_API_URL", DEFAULT_AGENT_API_URL),
            live_api_url=os.getenv("VINU_LIVE_API_URL", DEFAULT_LIVE_API_URL),
            capital_kelly_scale=float(os.getenv("VINU_CAPITAL_KELLY_SCALE", "0.25")),
            capital_max_position_pct=float(os.getenv("VINU_CAPITAL_MAX_POSITION_PCT", "0.25")),
            capital_min_history=int(os.getenv("VINU_CAPITAL_MIN_HISTORY", "20")),
            capital_fractional_shares=os.getenv("VINU_CAPITAL_FRACTIONAL_SHARES", "false").strip().lower() in ("1", "true", "yes", "on"),
            include_yaml_strategies=os.getenv("VINU_PORTFOLIO_INCLUDE_YAML_STRATEGIES", "false").strip().lower() in ("1", "true", "yes", "on"),
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
            reserve_fraction=float(os.getenv("VINU_PORTFOLIO_RESERVE_FRACTION", "0.0")),
            shared_root=(Path(_shared) if (_shared := os.getenv("VINU_SHARED_ROOT", "").strip()) else None),
            maturity_capital_gating_enabled=os.getenv(
                "VINU_PORTFOLIO_MATURITY_CAPITAL_GATING_ENABLED", "false"
            ).lower() in ("1", "true", "yes"),
            maturity_capital_multiplier_cold_start=float(
                os.getenv("VINU_PORTFOLIO_MATURITY_MULT_COLD_START", "0.1")
            ),
            maturity_capital_multiplier_paper_only=float(
                os.getenv("VINU_PORTFOLIO_MATURITY_MULT_PAPER_ONLY", "0.25")
            ),
            maturity_capital_multiplier_early_live=float(
                os.getenv("VINU_PORTFOLIO_MATURITY_MULT_EARLY_LIVE", "0.5")
            ),
        )


def load_config() -> PortfolioConfig:
    return PortfolioConfig.from_env()
