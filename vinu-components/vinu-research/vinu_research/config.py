from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

DEFAULT_FEATURES_API_URL = "http://127.0.0.1:8082"
DEFAULT_SIMULATOR_API_URL = "http://127.0.0.1:8085"
DEFAULT_CORRELATION_API_URL = "http://127.0.0.1:8083"
DEFAULT_STOCK_PRICE_API_URL = "http://127.0.0.1:8081"
DEFAULT_BENCHMARK_SYMBOL = "SPY"
DEFAULT_MAX_ITERATIONS = 5
DEFAULT_IMPROVEMENT_THRESHOLD = 0.05
DEFAULT_INITIAL_CAPITAL = 1_000_000.0
DEFAULT_DATA_ROOT = Path.cwd() / "data"
DEFAULT_LLM_BASE_URL = "http://127.0.0.1:11434/v1"
DEFAULT_LLM_MODEL = "llama3.2"
DEFAULT_LLM_TTL_SEC = 86400
DEFAULT_LLM_MAX_TOKENS = 8000

_env_loaded = False


def _ensure_dotenv_loaded(*, force: bool = False) -> None:
    global _env_loaded
    if _env_loaded and not force:
        return
    load_dotenv()
    _env_loaded = True


def _reset_env_for_testing() -> None:
    global _env_loaded
    _env_loaded = False


@dataclass
class ResearchConfig:
    features_api_url: str = DEFAULT_FEATURES_API_URL
    simulator_api_url: str = DEFAULT_SIMULATOR_API_URL
    correlation_api_url: str = DEFAULT_CORRELATION_API_URL
    max_iterations: int = DEFAULT_MAX_ITERATIONS
    improvement_threshold: float = DEFAULT_IMPROVEMENT_THRESHOLD
    initial_capital: float = DEFAULT_INITIAL_CAPITAL
    transaction_cost_pct: float = 0.001
    slippage_pct: float = 0.0005
    allow_short: bool = True
    # Bar granularity fed to the simulator ("1m","5m","15m","30m","1h","4h","1d").
    # Daily by default; matches vinu-simulator's CustomSimulateRequest.interval.
    interval: str = "1d"
    data_root: Path = DEFAULT_DATA_ROOT
    max_drawdown_threshold: float = -0.25
    llm_enabled: bool = False
    llm_base_url: str = DEFAULT_LLM_BASE_URL
    llm_model: str = DEFAULT_LLM_MODEL
    llm_api_key: str | None = None
    llm_ttl_sec: int = DEFAULT_LLM_TTL_SEC
    llm_max_tokens: int = DEFAULT_LLM_MAX_TOKENS
    llm_timeout_sec: float = 120.0
    llm_cache_path: str = ""
    # Enabled by default: without walk-forward, a run's reported Sharpe/MaxDD are
    # purely in-sample, fit to the exact data they're refined against.
    walk_forward_enabled: bool = True
    walk_forward_method: str = "expanding"
    walk_forward_windows: int = 3
    walk_forward_train_pct: float = 0.6
    walk_forward_test_pct: float = 0.2
    walk_forward_gap_days: int = 5
    walk_forward_min_train_days: int = 252
    walk_forward_step_size_days: int = 63
    stock_price_api_url: str = DEFAULT_STOCK_PRICE_API_URL
    benchmark_symbol: str = DEFAULT_BENCHMARK_SYMBOL
    generator_mode: str = "hybrid"
    llm_candidates: int = 3

    # True holdout: a trailing slice of the requested date range the refinement loop
    # never sees — filters are never chosen using this data. A PASS verdict is only
    # accepted if the strategy also clears this bar, not just the in-sample metrics
    # it was tuned against.
    holdout_fraction: float = 0.2
    holdout_gap_days: int = 5
    # A PASS candidate whose holdout Sharpe degrades by more than this fraction of
    # its in-sample Sharpe (or goes negative) is rejected and refinement continues.
    max_holdout_sharpe_degradation: float = 0.5
    # Never allow PASS on a thin sample, regardless of how good the Sharpe looks —
    # a handful of trades isn't enough to trust any ratio computed from them.
    min_trades_for_pass: int = 30

    # Portfolio-level analysis (only runs when a multi-symbol universe is passed to
    # StrategyResearchLoop.run()): correlation matrix + a beta-neutral hedge overlay
    # computed analytically from realized returns using a causal rolling beta.
    portfolio_beta_hedge_lookback_days: int = 60
    portfolio_beta_hedge_max_ratio: float = 1.5
    target_sharpe_ratio: float = 1.5
    target_max_drawdown: float = -0.30


@dataclass(frozen=True)
class DecayThresholds:
    ic_ratio_healthy: float = 0.7
    ic_ratio_warning: float = 0.5
    ic_ratio_critical: float = 0.3
    ir_healthy: float = 1.0
    ir_warning: float = 0.5
    ir_critical: float = 0.1
    ic_pos_healthy: float = 0.55
    ic_pos_warning: float = 0.45
    ic_pos_critical: float = 0.35
    sharpe_healthy: float = 1.0
    sharpe_warning: float = 0.5
    sharpe_critical: float = 0.0


def load_config(*, force_reload: bool = False) -> ResearchConfig:
    _ensure_dotenv_loaded(force=force_reload)
    data_root_raw = os.environ.get("VINU_RESEARCH_DATA_ROOT", "")
    data_root = Path(data_root_raw) if data_root_raw else DEFAULT_DATA_ROOT
    return ResearchConfig(
        features_api_url=os.environ.get("VINU_FEATURES_API_URL", DEFAULT_FEATURES_API_URL),
        simulator_api_url=os.environ.get("VINU_SIMULATOR_API_URL", DEFAULT_SIMULATOR_API_URL),
        correlation_api_url=os.environ.get("VINU_CORRELATION_API_URL", DEFAULT_CORRELATION_API_URL),
        max_iterations=int(os.environ.get("VINU_RESEARCH_MAX_ITERATIONS", str(DEFAULT_MAX_ITERATIONS))),
        improvement_threshold=float(os.environ.get("VINU_RESEARCH_IMPROVEMENT_THRESHOLD", str(DEFAULT_IMPROVEMENT_THRESHOLD))),
        initial_capital=float(os.environ.get("VINU_RESEARCH_INITIAL_CAPITAL", str(DEFAULT_INITIAL_CAPITAL))),
        transaction_cost_pct=float(os.environ.get("VINU_RESEARCH_TRANSACTION_COST_PCT", "0.001")),
        slippage_pct=float(os.environ.get("VINU_RESEARCH_SLIPPAGE_PCT", "0.0005")),
        allow_short=os.environ.get("VINU_RESEARCH_ALLOW_SHORT", "true").lower() == "true",
        interval=os.environ.get("VINU_RESEARCH_INTERVAL", "1d"),
        data_root=data_root,
        max_drawdown_threshold=float(os.environ.get("VINU_RESEARCH_MAX_DRAWDOWN_THRESHOLD", "-0.25")),
        llm_enabled=os.environ.get("VINU_RESEARCH_LLM_ENABLED", "false").lower() == "true",
        llm_base_url=os.environ.get("VINU_LLM_BASE_URL", DEFAULT_LLM_BASE_URL),
        llm_model=os.environ.get("VINU_LLM_MODEL", DEFAULT_LLM_MODEL),
        llm_api_key=os.environ.get("VINU_LLM_API_KEY") or None,
        llm_ttl_sec=int(os.environ.get("VINU_RESEARCH_LLM_TTL_SEC", str(DEFAULT_LLM_TTL_SEC))),
        llm_max_tokens=int(os.environ.get("VINU_LLM_MAX_TOKENS", str(DEFAULT_LLM_MAX_TOKENS))),
        llm_timeout_sec=float(os.environ.get("VINU_LLM_TIMEOUT_SEC", "120.0")),
        walk_forward_enabled=os.environ.get("VINU_RESEARCH_WALK_FORWARD", "true").lower() == "true",
        walk_forward_method=os.environ.get("VINU_RESEARCH_WF_METHOD", "expanding"),
        walk_forward_windows=int(os.environ.get("VINU_RESEARCH_WF_WINDOWS", "3")),
        walk_forward_train_pct=float(os.environ.get("VINU_RESEARCH_WF_TRAIN_PCT", "0.6")),
        walk_forward_test_pct=float(os.environ.get("VINU_RESEARCH_WF_TEST_PCT", "0.2")),
        walk_forward_gap_days=int(os.environ.get("VINU_RESEARCH_WF_GAP_DAYS", "5")),
        walk_forward_min_train_days=int(os.environ.get("VINU_RESEARCH_WF_MIN_TRAIN_DAYS", "252")),
        walk_forward_step_size_days=int(os.environ.get("VINU_RESEARCH_WF_STEP_DAYS", "63")),
        stock_price_api_url=os.environ.get("VINU_STOCK_PRICE_API_URL", DEFAULT_STOCK_PRICE_API_URL),
        benchmark_symbol=os.environ.get("VINU_RESEARCH_BENCHMARK_SYMBOL", DEFAULT_BENCHMARK_SYMBOL),
        generator_mode=os.environ.get("VINU_RESEARCH_GENERATOR_MODE", "hybrid"),
        llm_candidates=int(os.environ.get("VINU_RESEARCH_LLM_CANDIDATES", "3")),
        holdout_fraction=float(os.environ.get("VINU_RESEARCH_HOLDOUT_FRACTION", "0.2")),
        holdout_gap_days=int(os.environ.get("VINU_RESEARCH_HOLDOUT_GAP_DAYS", "5")),
        max_holdout_sharpe_degradation=float(
            os.environ.get("VINU_RESEARCH_MAX_HOLDOUT_SHARPE_DEGRADATION", "0.5")
        ),
        min_trades_for_pass=int(os.environ.get("VINU_RESEARCH_MIN_TRADES_FOR_PASS", "30")),
        portfolio_beta_hedge_lookback_days=int(
            os.environ.get("VINU_RESEARCH_PORTFOLIO_BETA_LOOKBACK_DAYS", "60")
        ),
        portfolio_beta_hedge_max_ratio=float(
            os.environ.get("VINU_RESEARCH_PORTFOLIO_BETA_MAX_RATIO", "1.5")
        ),
        target_sharpe_ratio=float(os.environ.get("VINU_RESEARCH_TARGET_SHARPE", "1.5")),
        target_max_drawdown=float(os.environ.get("VINU_RESEARCH_TARGET_MAX_DRAWDOWN", "-0.30")),
    )
