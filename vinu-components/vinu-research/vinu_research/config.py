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
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8087

_env_loaded = False


def _ensure_dotenv_loaded(*, force: bool = False) -> None:
    global _env_loaded
    if _env_loaded and not force:
        return
    load_dotenv()
    _env_loaded = True


def _reset_env_for_testing() -> None:
    """Clear cached dotenv state AND any already-exported VINU_* env vars.

    Resetting `_env_loaded` alone isn't enough: python-dotenv's load_dotenv()
    never overrides a variable already present in os.environ (its default
    override=False), so once a VINU_* var has been set once in this process
    (e.g. from a local .env file, or an earlier test), it silently persists
    across every later "reset" and test_load_config_defaults would assert
    against whatever leaked in rather than the real code defaults.
    """
    global _env_loaded
    _env_loaded = False
    for key in [k for k in os.environ if k.startswith("VINU_")]:
        del os.environ[key]


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
    # "llm"/"hybrid": LLM drives every iteration (fresh generation on iteration 1,
    # feedback-informed refinement on iteration 2+). "template": deterministic
    # recipe + rule-based filter injection only, no LLM — kept as the --no-llm
    # fallback but not being actively developed further for now.
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

    # BENCHING -> ACTIVE promotion bar. deflated_sharpe is the probability
    # best_sharpe reflects genuine skill after correcting for the cumulative
    # number of research trials run against the symbol (see deflated_sharpe_ratio);
    # 0.95 is the standard multiple-testing-corrected significance threshold.
    # holdout_required additionally demands the strategy passed the true
    # out-of-sample holdout check (if one could be computed for the run).
    promotion_deflated_sharpe_threshold: float = 0.95
    promotion_holdout_required: bool = True
    promotion_stress_test_required: bool = True
    # Cross-strategy correlation gate: before promoting, the candidate's daily
    # returns are compared against all ACTIVE strategies. If the average pairwise
    # correlation exceeds this threshold, promotion is blocked and the artifact
    # is created as BENCHING instead of ACTIVE.
    promotion_correlation_threshold: float = 0.85
    promotion_correlation_required: bool = False

    # Fixed historical crisis windows the winning strategy is replayed through
    # once, after the refinement loop finishes — never used to pick or tune
    # the strategy, unlike walk-forward/holdout windows carved from the
    # researched range itself. (name, from_date, to_date).
    stress_test_enabled: bool = True
    stress_test_windows: list[tuple[str, str, str]] = field(default_factory=lambda: [
        ("2020_covid_crash", "2020-02-15", "2020-04-15"),
        ("2022_rate_hike_drawdown", "2022-01-01", "2022-10-15"),
    ])
    # A window "fails" if max_drawdown during it breaches this (e.g. -50%) —
    # deliberately lenient: crisis windows are *expected* to hurt, this is
    # meant to catch catastrophic/leveraged blowups, not ordinary drawdown.
    stress_test_max_drawdown_threshold: float = -0.50

    # Re-validation: how often an ACTIVE artifact should be re-backtested against
    # fresh data to check for decay (in days). Also controls the lookback window
    # used for the re-validation backtest. Set to 0 to disable.
    revalidation_interval_days: int = 30
    revalidation_lookback_days: int = 180

    # Freshness Contract's regime/correlation recompute (04-agentic-still-
    # refinement's either/or with vinu-initial-analysis — hosted here since
    # it's the cheaper option: no new executor, one more scan on the
    # existing hourly loop's cadence). Daily, not hourly — regime moves
    # slower than a strategy's rolling Sharpe. Set to 0 to disable.
    regime_recompute_interval_days: int = 1

    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT


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
        promotion_deflated_sharpe_threshold=float(
            os.environ.get("VINU_RESEARCH_PROMOTION_DSR_THRESHOLD", "0.95")
        ),
        promotion_holdout_required=os.environ.get(
            "VINU_RESEARCH_PROMOTION_HOLDOUT_REQUIRED", "true"
        ).lower() in ("1", "true", "yes"),
        promotion_stress_test_required=os.environ.get(
            "VINU_RESEARCH_PROMOTION_STRESS_TEST_REQUIRED", "true"
        ).lower() in ("1", "true", "yes"),
        promotion_correlation_threshold=float(
            os.environ.get("VINU_RESEARCH_PROMOTION_CORRELATION_THRESHOLD", "0.85")
        ),
        promotion_correlation_required=os.environ.get(
            "VINU_RESEARCH_PROMOTION_CORRELATION_REQUIRED", "false"
        ).lower() in ("1", "true", "yes"),
        stress_test_enabled=os.environ.get("VINU_RESEARCH_STRESS_TEST_ENABLED", "true").lower()
        in ("1", "true", "yes"),
        stress_test_max_drawdown_threshold=float(
            os.environ.get("VINU_RESEARCH_STRESS_TEST_MAX_DD", "-0.50")
        ),
        revalidation_interval_days=int(
            os.environ.get("VINU_RESEARCH_REVALIDATION_INTERVAL_DAYS", "30")
        ),
        revalidation_lookback_days=int(
            os.environ.get("VINU_RESEARCH_REVALIDATION_LOOKBACK_DAYS", "180")
        ),
        regime_recompute_interval_days=int(
            os.environ.get("VINU_RESEARCH_REGIME_RECOMPUTE_INTERVAL_DAYS", "1")
        ),
        host=os.environ.get("VINU_RESEARCH_HOST", DEFAULT_HOST),
        port=int(os.environ.get("VINU_RESEARCH_PORT", str(DEFAULT_PORT))),
    )
