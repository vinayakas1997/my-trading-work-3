from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

from vinu_infra.secrets_loader import load_secret

DEFAULT_FEATURES_API_URL = "http://127.0.0.1:8082"
DEFAULT_SIMULATOR_API_URL = "http://127.0.0.1:8085"
DEFAULT_CORRELATION_API_URL = "http://127.0.0.1:8083"
DEFAULT_STOCK_PRICE_API_URL = "http://127.0.0.1:8081"
# Same shared VINU_AGENT_API_URL other services (e.g. vinu-live's
# orchestrator) already read for this address -- not a new
# VINU_RESEARCH_-scoped var, since this is the one canonical agent-api URL.
DEFAULT_AGENT_API_URL = "http://127.0.0.1:8086"
DEFAULT_SCREENER_API_URL = "http://127.0.0.1:8095"
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
    walk_forward_stability_threshold: float = 0.5
    walk_forward_min_completed_windows: int = 2
    stock_price_api_url: str = DEFAULT_STOCK_PRICE_API_URL
    agent_api_url: str = DEFAULT_AGENT_API_URL
    screener_api_url: str = DEFAULT_SCREENER_API_URL
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
    # Stage 2 (how-to-make-it-live.md #19): PBO was computed at research time
    # but never checked again at promotion -- the warning vanished the
    # moment the live response was read. 0.7 matches sweep_grid.py's
    # existing pbo_severe convention for the sweep-recipe path; same
    # required-by-default posture as holdout/stress_test above (None because
    # too few splits to compute it, same as an unset holdout, is a reason to
    # withhold promotion, not a reason to wave it through).
    promotion_pbo_threshold: float = 0.7
    promotion_pbo_required: bool = True
    # Cross-strategy correlation gate: before promoting, the candidate's daily
    # returns are compared against all ACTIVE strategies. If the average pairwise
    # correlation exceeds this threshold, promotion is blocked and the artifact
    # is created as BENCHING instead of ACTIVE.
    promotion_correlation_threshold: float = 0.85
    # Was False -- the gate existed and worked (check_correlation_gate
    # already handles the fail-closed path correctly) but defaulted off, so
    # a highly-correlated candidate could still be promoted to ACTIVE
    # unless something else caught it. The separate runtime trim monitor in
    # vinu-live's orchestrator.py only ever cuts an ALREADY-open position at
    # the same 0.85 threshold -- it never blocks a new promotion from being
    # correlated in the first place. Flipped to True so promotion-time and
    # runtime correlation awareness are both actually engaged.
    promotion_correlation_required: bool = True

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
    # Stage C (C13): in addition to the fixed windows above, derive extra
    # stress windows from *this symbol's* own price path over the researched
    # range — its deepest drawdown, sharpest run-up, steepest decline — and
    # replay the winning strategy through those too. Additive, opt-in (the
    # fixed windows are unchanged). Env: VINU_RESEARCH_STRESS_DERIVE_REGIME_WINDOWS.
    stress_test_derive_regime_windows: bool = False

    # Researcher Role d — paper-trade rehearsal (04:245). Runs the winning
    # sweep candidate through a trailing historical window bar-by-bar (same
    # simulator + T+1 + cost model) before it reaches risk_gatekeeper.
    # Default 7 calendar days ≈ 5 trading days: short enough to be a
    # live-like check, long enough to require a real fill.
    paper_rehearsal_enabled: bool = True
    paper_rehearsal_lookback_days: int = 7
    paper_rehearsal_max_sharpe_degradation: float = 0.5

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

    # High-expectations spec #6 -- whole-market regime analogue engine
    # (market_regime_analogue.py). Opt-in, same cautious-rollout posture as
    # stress_test_derive_regime_windows above and VINU_LIVE_OOD_DETECTOR's
    # "off" default: an extra benchmark-symbol fetch + KNN pass per day
    # (cached, not per trade-plan call) feeding compute_trade_score's
    # regime_fit_score, which already defaults to 0 (not skipped) when this
    # is off. Env: VINU_RESEARCH_REGIME_ANALOGUE_ENABLED.
    regime_analogue_enabled: bool = False
    regime_analogue_benchmark_symbol: str = "SPY"

    # High-expectations spec #7 -- live options-IV context (trade_plan_
    # authoring.fetch_options_context), opt-in for the same reason: an
    # extra per-symbol external API call on every authoring run (not day-
    # cacheable like the regime analogue above -- IV moves intraday), and
    # requires an Alpaca account with options-data entitlement, which not
    # every deployment has. Env: VINU_RESEARCH_OPTIONS_IV_ENABLED.
    options_iv_enabled: bool = False

    # investment_committee debate signal (trade_plan_authoring.
    # fetch_debate_signal) -- opt-in since it depends on
    # VINU_AGENT_DEBATE_MODE=full (itself opt-in) already having produced a
    # completed debate for this symbol; an extra cross-service HTTP round
    # trip on every authoring run for a feature most deployments won't have
    # populated. Env: VINU_RESEARCH_DEBATE_SIGNAL_ENABLED.
    debate_signal_enabled: bool = False
    # fetch_debate_signal used to hardcode strength=0.5 regardless of how
    # strongly the risk_officer's text reads -- this multiplier applies on
    # top of the conviction-tier strength (0.4/0.7/1.0) the parser now
    # derives from the text, so the debate's overall influence on
    # _confluence_score can be tuned independently of a single raw angle's
    # typical strength range without touching the gate itself. 1.0 = no
    # extra weighting beyond the conviction tier.
    debate_signal_weight: float = 1.0

    # MaturityAssessor (maturity_assessor.py), wired into the forecast
    # prompt -- opt-in, same cautious-rollout posture as regime_analogue_
    # enabled above (cheap, local computation, but it changes prompt
    # content, so it doesn't default on). Env: VINU_RESEARCH_MATURITY_
    # TIER_ENABLED. `agent_data_root`, when set, points at a read-only
    # mount of vinu-agent's own data root (paper_performance.db) --
    # only real on `agent-api` (the in-process trade-plan-authoring
    # path); left unset on `research-api` (the HTTP fallback path), where
    # MaturityAssessor still runs but can't distinguish cold_start from
    # paper_only (see maturity_assessor.py's own docstring). Env:
    # VINU_RESEARCH_AGENT_DATA_ROOT.
    maturity_tier_enabled: bool = False
    agent_data_root: Path | None = None

    # Regime router for the LLM trade-plan pipeline (high-expectations
    # follow-up): mirrors vinu-portfolio's own already-proven
    # _regime_alignment_multiplier / regime_tilt_bound design (same default
    # magnitude, same "bounded tilt, not a hard switch" shape) -- that
    # router only reaches the rule-based vinu-strategy YAML pipeline, this
    # gives current_regime (regime_analysis angle) a second, direct channel
    # into THIS pipeline's position sizing, independent of its existing
    # (diluted, one-vote-among-many) confluence-score signal. On by
    # default, same as vinu-portfolio's own tilt -- 0.0 disables it.
    # Env: VINU_RESEARCH_REGIME_SIZE_TILT_BOUND.
    regime_size_tilt_bound: float = 0.3

    # Screener-rank sizing tilt: a second, independent optional channel
    # into position sizing, same bounded-tilt shape as regime_size_tilt_
    # bound above -- a symbol's percentile rank in vinu-screener's latest
    # run for screener_ranker_id nudges size up/down. Unlike regime (on
    # by default, since regime_analysis angle rows always exist once
    # computed), this ships inert: screener_ranker_id is empty by
    # default, so no fetch is ever attempted unless an operator
    # deliberately points it at a real ranker_id -- most deployments
    # won't have one configured. Env: VINU_RESEARCH_SCREENER_RANKER_ID,
    # VINU_RESEARCH_SCREENER_RANK_SIZE_TILT_BOUND.
    screener_ranker_id: str = ""
    screener_rank_size_tilt_bound: float = 0.3

    # Self-calibrating TradeScore weights (high-expectations follow-up, see
    # trade_score_calibration.py). Stays inert (no adjustment) below
    # min_sample real closed trades -- fitting weights against noise would
    # be worse than the honest heuristic default. `bound` caps how much any
    # single sub-score's weight can move in one calibration cycle (0.2 =
    # 20%), never a full refit. Env: VINU_RESEARCH_TRADE_SCORE_CALIBRATION_MIN_SAMPLE / _BOUND.
    trade_score_calibration_min_sample: int = 30
    trade_score_calibration_bound: float = 0.2

    # Sweep knobs (10-env-knobs.md): intervals + topN + fast flags. Env only, no code change to flip.
    sweep_intervals: str = "1d,1H,15min"
    sweep_top_n_per_interval: int = 3
    sweep_use_vectorbt: bool = True
    sweep_vectorbt_concurrency: int = 5
    sweep_use_hyperopt: bool = True
    sweep_hyperopt_max_points: int = 8
    sweep_diversity_required: bool = True
    sweep_min_succeeds_for_pass: int = 2

    def sweep_interval_list(self) -> list[str]:
        """Ordered intervals, 1D first (07 No.1): callers run 1d before 1H
        before 15min so slower, more-trusted evidence lands first."""
        order = {"1d": 0, "1D": 0, "1h": 1, "1H": 1, "15min": 2, "15m": 2}
        parts = [p.strip() for p in (self.sweep_intervals or "").split(",") if p.strip()]
        return sorted(parts, key=lambda p: order.get(p, 99))

    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT


@dataclass(frozen=True)
class TradeScoreThresholds:
    """High-expectations spec #14's Trade Score tiers/weights. Same
    standalone-frozen-dataclass-with-defaults shape as DecayThresholds below
    (not a ResearchConfig field, not read via load_config) -- instantiate
    directly (`TradeScoreThresholds()`), override only in tests or a future
    calibration pass. See gates/trade_score_gate.py for how each is used.
    """
    # Tier cutoffs (spec: >110 strong, 90-110 moderate, 70-90 watch, <70 no_trade).
    strong_threshold: float = 110.0
    moderate_threshold: float = 90.0
    watch_threshold: float = 70.0
    # Sub-score max points; total_score's ceiling is their sum (135, matching
    # the spec's own 135-point example).
    confluence_max: float = 40.0
    ev_max: float = 35.0
    risk_max: float = 30.0
    regime_fit_max: float = 30.0
    # Net-EV-net-of-costs level treated as a full ev_score -- a documented
    # heuristic (2%), not a fitted threshold.
    ev_full_score_pct: float = 0.02
    # expected_drawdown/cvar level treated as a zero risk_score -- also a
    # documented heuristic (10%), not a fitted threshold.
    risk_full_loss_pct: float = 0.10
    # Cost estimate (basis points) used by _ev_score when market_state has no
    # liquidity-derived cost_bps.
    default_cost_bps: float = 10.0
    # High-expectations spec #7: scales market_state.options' ATM IV into an
    # extra EV-reducing uncertainty cost in _ev_score -- a documented
    # heuristic, not a fitted coefficient (e.g. atm_iv=0.30 -> 0.015, a
    # 1.5% haircut on expected value).
    iv_uncertainty_weight: float = 0.05
    # check_trade_score_gate() blocks approval below this tier.
    min_tradeable_tier: str = "watch"
    # Reward:risk hard veto (high-expectations spec's asymmetry pillar --
    # "no R:R>=X veto" was a real gap: R:R only implicitly nudged ev_score/
    # risk_score before this). forecast.magnitude_pct / risk_band.
    # expected_drawdown below this forces tier to "no_trade" regardless of
    # the composite score -- an explicit veto, not a sub-score penalty.
    min_reward_risk_ratio: float = 1.5


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
        llm_api_key=load_secret("vinu_llm_api_key", "VINU_LLM_API_KEY") or None,
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
        walk_forward_stability_threshold=float(os.environ.get("VINU_RESEARCH_WF_STABILITY_THRESHOLD", "0.5")),
        walk_forward_min_completed_windows=int(os.environ.get("VINU_RESEARCH_WF_MIN_COMPLETED_WINDOWS", "2")),
        stock_price_api_url=os.environ.get("VINU_STOCK_PRICE_API_URL", DEFAULT_STOCK_PRICE_API_URL),
        agent_api_url=os.environ.get("VINU_AGENT_API_URL", DEFAULT_AGENT_API_URL),
        screener_api_url=os.environ.get("VINU_SCREENER_API_URL", DEFAULT_SCREENER_API_URL),
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
        promotion_pbo_threshold=float(
            os.environ.get("VINU_RESEARCH_PROMOTION_PBO_THRESHOLD", "0.7")
        ),
        promotion_pbo_required=os.environ.get(
            "VINU_RESEARCH_PROMOTION_PBO_REQUIRED", "true"
        ).lower() in ("1", "true", "yes"),
        promotion_correlation_threshold=float(
            os.environ.get("VINU_RESEARCH_PROMOTION_CORRELATION_THRESHOLD", "0.85")
        ),
        promotion_correlation_required=os.environ.get(
            "VINU_RESEARCH_PROMOTION_CORRELATION_REQUIRED", "true"
        ).lower() in ("1", "true", "yes"),
        stress_test_enabled=os.environ.get("VINU_RESEARCH_STRESS_TEST_ENABLED", "true").lower()
        in ("1", "true", "yes"),
        stress_test_max_drawdown_threshold=float(
            os.environ.get("VINU_RESEARCH_STRESS_TEST_MAX_DD", "-0.50")
        ),
        stress_test_derive_regime_windows=os.environ.get(
            "VINU_RESEARCH_STRESS_DERIVE_REGIME_WINDOWS", "false"
        ).lower() in ("1", "true", "yes"),
        paper_rehearsal_enabled=os.environ.get(
            "VINU_RESEARCH_PAPER_REHEARSAL_ENABLED", "true"
        ).lower() in ("1", "true", "yes"),
        paper_rehearsal_lookback_days=int(
            os.environ.get("VINU_RESEARCH_PAPER_REHEARSAL_LOOKBACK_DAYS", "7")
        ),
        paper_rehearsal_max_sharpe_degradation=float(
            os.environ.get("VINU_RESEARCH_PAPER_REHEARSAL_MAX_DEGRADATION", "0.5")
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
        regime_analogue_enabled=os.environ.get(
            "VINU_RESEARCH_REGIME_ANALOGUE_ENABLED", "false"
        ).lower() in ("1", "true", "yes"),
        regime_analogue_benchmark_symbol=os.environ.get(
            "VINU_RESEARCH_REGIME_ANALOGUE_BENCHMARK_SYMBOL", "SPY"
        ),
        options_iv_enabled=os.environ.get(
            "VINU_RESEARCH_OPTIONS_IV_ENABLED", "false"
        ).lower() in ("1", "true", "yes"),
        debate_signal_enabled=os.environ.get(
            "VINU_RESEARCH_DEBATE_SIGNAL_ENABLED", "false"
        ).lower() in ("1", "true", "yes"),
        debate_signal_weight=float(os.environ.get("VINU_RESEARCH_DEBATE_SIGNAL_WEIGHT", "1.0")),
        maturity_tier_enabled=os.environ.get(
            "VINU_RESEARCH_MATURITY_TIER_ENABLED", "false"
        ).lower() in ("1", "true", "yes"),
        agent_data_root=(
            Path(os.environ["VINU_RESEARCH_AGENT_DATA_ROOT"])
            if os.environ.get("VINU_RESEARCH_AGENT_DATA_ROOT")
            else None
        ),
        regime_size_tilt_bound=float(os.environ.get("VINU_RESEARCH_REGIME_SIZE_TILT_BOUND", "0.3")),
        screener_ranker_id=os.environ.get("VINU_RESEARCH_SCREENER_RANKER_ID", ""),
        screener_rank_size_tilt_bound=float(os.environ.get("VINU_RESEARCH_SCREENER_RANK_SIZE_TILT_BOUND", "0.3")),
        trade_score_calibration_min_sample=int(
            os.environ.get("VINU_RESEARCH_TRADE_SCORE_CALIBRATION_MIN_SAMPLE", "30")
        ),
        trade_score_calibration_bound=float(
            os.environ.get("VINU_RESEARCH_TRADE_SCORE_CALIBRATION_BOUND", "0.2")
        ),
        sweep_intervals=os.environ.get("VINU_SWEEP_INTERVALS", "1d,1H,15min"),
        sweep_top_n_per_interval=int(os.environ.get("VINU_SWEEP_TOP_N_PER_INTERVAL", "3")),
        sweep_use_vectorbt=os.environ.get("VINU_SWEEP_USE_VECTORBT", "true").lower() in ("1", "true", "yes"),
        sweep_vectorbt_concurrency=int(os.environ.get("VINU_SWEEP_VECTORBT_CONCURRENCY", "5")),
        sweep_use_hyperopt=os.environ.get("VINU_SWEEP_USE_HYPEROPT", "true").lower() in ("1", "true", "yes"),
        sweep_hyperopt_max_points=int(os.environ.get("VINU_SWEEP_HYPEROPT_MAX_POINTS", "8")),
        sweep_diversity_required=os.environ.get("VINU_SWEEP_DIVERSITY_REQUIRED", "true").lower() in ("1", "true", "yes"),
        sweep_min_succeeds_for_pass=int(os.environ.get("VINU_SWEEP_MIN_SUCCEEDS_FOR_PASS", "2")),
        host=os.environ.get("VINU_RESEARCH_HOST", DEFAULT_HOST),
        port=int(os.environ.get("VINU_RESEARCH_PORT", str(DEFAULT_PORT))),
    )
