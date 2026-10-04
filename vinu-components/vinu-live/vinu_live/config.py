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
DEFAULT_STRATEGY_API_URL = "http://127.0.0.1:8084"
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
    strategy_api_url: str = DEFAULT_STRATEGY_API_URL
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
    # Stage 0 (G2a, research-discussion-v1/complete-plan/01-native-gaps.md):
    # scans CREATED trade_plan artifacts and calls their approve endpoint
    # (bootstrap-gated -- see trade_plan_authoring.approve_trade_plan).
    # Matches trade_plan_worker_interval_sec's own cadence rather than
    # inventing a separate number -- a freshly authored plan is worth
    # approving on roughly the same cadence it gets evaluated on.
    trade_plan_approval_worker_interval_sec: int = 300
    # Point 2's candle-close poller (reverse-engineering/
    # 03-poller-and-state-schema.md Part A) -- needs to be meaningfully
    # shorter than the shortest strategy timeframe in use so a candle
    # close is detected promptly. A guessed starting constant, same
    # posture as the other worker intervals in this file.
    live_decision_poll_interval_sec: int = 60
    # high-expectations follow-up, point #2 of 00-maturity-agentic-system-
    # explanation.md's own step-3 phasing ("risk_gatekeeper/
    # capital_allocator wiring... still not started"). Opt-in, off by
    # default, same cautious-rollout posture every other maturity-tier
    # consumer in this codebase already uses (`maturity_tier_enabled` in
    # vinu-research). Point #3's own knob (live_decision) does NOT belong
    # here -- reverse-engineering/06-execution-handoff-and-architecture.md
    # point 8 confirms the real deciding agent lives in vinu-agent, not
    # vinu-live (this service only has the poller/detector/tracker), so
    # that knob is `AgentConfig.live_decision_maturity_scaling_enabled` in
    # vinu-agent/vinu_agent/config.py instead. An earlier version of this
    # file had a same-named, unused field here -- removed once this got
    # verified rather than left as dead config.
    risk_gatekeeper_maturity_scaling_enabled: bool = False
    # Exit mechanism for live_decision-opened positions (missing-pieces-of-
    # system/new-theory-of-trading/system-wide-audit-and-design/
    # 04-synthesis-built-vs-missing-2026-09-28.md): how many bars must pass
    # between position-review calls to live_decision_agent for an already-
    # open position. A guessed starting constant, same posture as
    # grace_window_bars' own default (10) and RECON_DRIFT_ALERT_CYCLES (3)
    # -- not independently tuned.
    live_decision_position_review_cadence_bars: int = 5
    # logic-audit-2026-10-02 A4 (the-inconsistencies-v2): the trade-plan
    # orchestrator pauses NEW exposure on a consecutive-loss cooldown, a stale
    # price feed and extreme realized vol; this scheduler path had none of
    # them. When on, those three guards gate only the instructions that
    # increase exposure (never a reduce/close). Off by default -- it changes
    # live order flow, so it ships opt-in like every other behavior change in
    # this codebase; the orchestrator's own guards stay on regardless.
    scheduler_entry_guards_enabled: bool = False
    # logic-audit-2026-10-03 (v1 C1 + a worse bug found while fixing it): a pair
    # whose live-decision call failed / came back unrecognized stayed
    # ready_to_execute FOREVER -- the poller only triggers on a fresh transition
    # INTO that stage and the state tracker deliberately never re-evaluates a
    # ready pair, so the log's "will retry next cycle" was false. Now: retry on
    # each later candle, and after this many unresolved attempts (error /
    # unrecognized / EXTEND_GRACE_WINDOW) expire the trigger, record it, and
    # notify -- the pair then resets to idle and can fire again. 0 restores the
    # old never-retry behavior.
    live_decision_max_trigger_attempts: int = 3
    # logic-audit-2026-10-02 A7: a FAILED read of a configured broker's equity
    # (exception, non-200, or a reply without a usable equity) used to fall
    # through to "positions x price" or fallback_portfolio_value (1,000,000), so
    # target weights were multiplied by an invented figure. When on, the
    # scheduler cycle aborts instead (like the positions / portfolio fetches).
    # `configured: false` (no broker at all) still uses the placeholder. Off by
    # default (changes live behavior); applies to LiveScheduler only -- the
    # orchestrator also sizes EXITS from this value, so it keeps its fallback.
    abort_on_equity_read_failure: bool = False
    # logic-audit-2026-10-02 A5: in the trade-plan orchestrator exits are
    # reduce_only and every guard is ENTRIES-ONLY, so a halt never traps a
    # position. On this scheduler path a breaker HALT, the kill switch, a wide
    # spread or an earnings blackout blocked sells as well as buys, and orders
    # carried no reduce_only flag. When on, instructions that only shrink or
    # close a position are tagged, sent with reduce_only=true, and are exempt
    # from the breaker-halt skip, the kill-switch skip (the agent-side
    # OrderGuard still applies its own halt policy), and the spread/event gate
    # (they go as market orders). Anything that increases exposure is gated
    # exactly as before. ON by default (2026-10-04, features-logic-checking): a halt must never trap a closing
    # sell. Env VINU_LIVE_SCHEDULER_EXITS_EXEMPT_FROM_HALTS=false turns it off.
    scheduler_exits_exempt_from_halts: bool = True
    # When the broker (through the agent API) cannot be read -- positions read fails, a configured broker's equity
    # cannot be read, or order submissions fail at the HTTP / broker level -- say so LOUDLY: an ERROR log, a
    # `broker_unreachable` list in the cycle result, and one CRITICAL notification on the first bad cycle, a
    # reminder every `broker_unreachable_renotify_cycles` consecutive bad cycles, and one "recovered" message.
    # Notification only: it never changes what the scheduler does. ON by default. Env:
    # VINU_LIVE_BROKER_UNREACHABLE_NOTIFY_ENABLED, VINU_LIVE_BROKER_UNREACHABLE_RENOTIFY_CYCLES.
    broker_unreachable_notify_enabled: bool = True
    broker_unreachable_renotify_cycles: int = 6
    # Append-only ledger of every order slice the scheduler tried to place (or skipped, with the reason): reference
    # price it was sized at, spread at decision time, order type, and the broker's submission answer, in
    # `<data_root>/execution_log.db` (see execution_log.py). Log-only: it never changes an order, and a write
    # failure is swallowed. ON by default; off = no file is created.
    execution_log_enabled: bool = True
    # At the start of each cycle, look up the broker's current state of recent accepted orders and write their
    # fill price / filled quantity / status and the slippage against the decision-time quote mid into the ledger.
    # Read-only toward the broker; never changes an order. `batch` bounds the lookups per cycle.
    # Env: VINU_LIVE_EXECUTION_FILL_ENRICHMENT_ENABLED, VINU_LIVE_EXECUTION_FILL_ENRICHMENT_BATCH.
    execution_fill_enrichment_enabled: bool = True
    execution_fill_enrichment_batch: int = 25
    # inconsistencies v1 A8: the live-decision agent states `precondition_held`
    # (did the strategy's own falsifiable precondition hold?) with every EXECUTE,
    # but only the agent's prompt reads it -- an EXECUTE with precondition_held
    # == false became an order exactly like one with true. When on, the scheduler
    # does NOT open a position for an EXECUTE whose precondition_held is False
    # (None / unknown still passes: fail-open). The decision is marked applied
    # (final information, not retried) and reported as `precondition_blocked` in
    # the cycle result. Positions already open are untouched. Off by default.
    precondition_enforcing_enabled: bool = False
    # logic-audit-2026-10-02 A6: the scheduler's breaker checked the trade-plan
    # BOOK (positions the orchestrator opened; this path writes nothing to it) and
    # tested REALIZED loss only, so the positions the scheduler actually trades
    # and an open drawdown were invisible to it. When on, its position-count /
    # leverage / cluster checks run over the live BROKER positions, and its daily
    # loss is (equity now - the first equity this scheduler saw today, UTC), which
    # includes unrealized moves. Falls back to the book / realized P&L for any
    # input it cannot get. ON by default (2026-10-04, features-logic-checking): the 5% daily-loss breaker must see
    # the positions the scheduler really trades. Env VINU_LIVE_SCHEDULER_BREAKER_USES_BROKER_ACCOUNT=false turns it off.
    scheduler_breaker_uses_broker_account: bool = True
    # logic-audit-2026-10-02 A1: the hourly scheduler sized orders from
    # /portfolio/state (raw risk-parity weights). The regime / outcome tilts, the
    # drawdown ladder (halve / flat / halt), the maturity capital ladder and the
    # reserve fraction are all computed by /portfolio/daily-allocation and were
    # discarded. When on, the scheduler reads daily-allocation instead: it takes
    # its tilted `weights` and scales them by deployable_equity / account_equity
    # (clamped to [0, 1]) so "halve" really deploys half the capital and "flat" /
    # "halt" really ask for no positions (exits go through, see
    # scheduler_exits_exempt_from_halts). If daily-allocation cannot be read the
    # scheduler falls back to /portfolio/state (today's behavior) and says so in
    # the cycle result. Live-decision weights are never scaled by this.
    scheduler_use_daily_allocation: bool = False
    # logic-audit-2026-10-02 A2: two executors share one broker account and the
    # scheduler liquidated any broker position it had no target for -- including
    # positions the trade-plan orchestrator opened. When on, the scheduler treats
    # a symbol as orchestrator-owned if it has an OPEN position in the trade-plan
    # book or an ACTIVE trade_plan artifact, and then neither trades it nor
    # targets it (the orchestrator is the single sizing authority for that symbol).
    # If ownership cannot be determined (active-plan read failed) it also leaves
    # every position that has no target this cycle alone, rather than guessing.
    scheduler_respect_trade_plan_symbols: bool = False
    # Companion to scheduler_respect_trade_plan_symbols: comma-separated symbols the scheduler opened BEFORE its order
    # ledger existed (so the ledger cannot know they are its own). Treated as scheduler-owned: if nothing targets them
    # any more they are closed. Everything not in the ledger and not listed here is left alone. Env:
    # VINU_LIVE_SCHEDULER_ADOPTED_SYMBOLS.
    scheduler_adopted_symbols: str = ""
    # logic-audit-2026-10-02 A8: the live-decision poller computes features on the
    # minimum warmup window (201 bars). An EMA-200 has not converged in that many
    # bars (up to ~4% off the backtest value), so a must-condition near an EMA-200
    # boundary can evaluate differently live than in backtest. When > 0, the
    # poller fetches max(minimum warmup, this) bars instead (measured: 600 bars
    # -> ema_200 within ~0.06% of backtest; 800 -> ~0.005%). 0 = old behavior.
    # Costs a larger bars fetch per new candle. Cumulative indicators (obv,
    # accumulation_distribution_line, vwap) stay window-dependent regardless.
    live_decision_feature_window_bars: int = 0

    # v2 audit S2: ask vinu-stock-price for CLOSED bars only, so a candle-close decision never evaluates a bar
    # that is still forming (its first minute looks like a new candle to the cursor). Off = old behaviour.
    live_decision_closed_bars_only: bool = False

    # v2 B1: input-novelty check. Off by default. When on, each new candle's live snapshot is compared with the
    # ticker's own recorded snapshot history (novelty.py); the result is logged, recorded as a `live_novelty`
    # snapshot row, written to the `live_decision.input_novelty` edge, and -- when high -- passed to the
    # live-decision agent as a caution. Never blocks anything by itself (log-only first, enforce later).
    # features-logic-checking F4: resolve the outcome of every live-fired signal trigger once its horizon has
    # elapsed (forward return / best / worst excursion over `live_decision_signal_horizon_bars` closed bars,
    # the same 20-bar horizon and formulas as the signal_evidence angle), so the evidence the deciding agent
    # reads for a live strategy's own must-condition gains outcomes. Recording only; never affects an order.
    live_decision_signal_outcomes_enabled: bool = True
    live_decision_signal_horizon_bars: int = 20
    # An agent run is several LLM calls plus tool reads, so it takes far longer than the 30 s the poller's HTTP client
    # allows other calls. With the old 30 s a slow (local) model made every decision call fail with an empty message.
    live_decision_agent_timeout_sec: float = 300.0
    # A live-decision strategy may open positions only after research validated its exact rules (and only on the tickers
    # that passed). ON by default; it was effectively off before, which let unvalidated 15-minute and 1-hour strategies
    # go live. Switching it off is a deliberate act that a test guards.
    live_decision_require_validated_strategy: bool = True

    live_decision_novelty_enabled: bool = False
    live_decision_novelty_ratio: float = 2.0
    live_decision_novelty_min_reference: int = 30
    live_decision_novelty_reference_rows: int = 250

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
            strategy_api_url=os.getenv("VINU_STRATEGY_API_URL", DEFAULT_STRATEGY_API_URL),
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
            trade_plan_approval_worker_interval_sec=int(
                os.getenv("VINU_LIVE_TRADE_PLAN_APPROVAL_INTERVAL", "300"),
            ),
            live_decision_poll_interval_sec=int(
                os.getenv("VINU_LIVE_DECISION_POLL_INTERVAL", "60"),
            ),
            risk_gatekeeper_maturity_scaling_enabled=os.getenv(
                "VINU_LIVE_RISK_GATEKEEPER_MATURITY_SCALING_ENABLED", "false",
            ).lower() in ("1", "true", "yes"),
            live_decision_position_review_cadence_bars=int(
                os.getenv("VINU_LIVE_DECISION_POSITION_REVIEW_CADENCE_BARS", "5"),
            ),
            scheduler_entry_guards_enabled=os.getenv(
                "VINU_LIVE_SCHEDULER_ENTRY_GUARDS_ENABLED", "false",
            ).lower() in ("1", "true", "yes"),
            live_decision_max_trigger_attempts=int(
                os.getenv("VINU_LIVE_DECISION_MAX_TRIGGER_ATTEMPTS", "3"),
            ),
            abort_on_equity_read_failure=os.getenv(
                "VINU_LIVE_ABORT_ON_EQUITY_READ_FAILURE", "false",
            ).lower() in ("1", "true", "yes"),
            scheduler_exits_exempt_from_halts=os.getenv(
                "VINU_LIVE_SCHEDULER_EXITS_EXEMPT_FROM_HALTS", "true",
            ).lower() in ("1", "true", "yes"),
            scheduler_use_daily_allocation=os.getenv(
                "VINU_LIVE_SCHEDULER_USE_DAILY_ALLOCATION", "false",
            ).lower() in ("1", "true", "yes"),
            scheduler_respect_trade_plan_symbols=os.getenv(
                "VINU_LIVE_SCHEDULER_RESPECT_TRADE_PLAN_SYMBOLS", "false",
            ).lower() in ("1", "true", "yes"),
            scheduler_breaker_uses_broker_account=os.getenv(
                "VINU_LIVE_SCHEDULER_BREAKER_USES_BROKER_ACCOUNT", "true",
            ).lower() in ("1", "true", "yes"),
            precondition_enforcing_enabled=os.getenv(
                "VINU_LIVE_PRECONDITION_ENFORCING_ENABLED", "false",
            ).lower() in ("1", "true", "yes"),
            execution_log_enabled=os.getenv(
                "VINU_LIVE_EXECUTION_LOG_ENABLED", "true",
            ).lower() in ("1", "true", "yes"),
            scheduler_adopted_symbols=os.getenv("VINU_LIVE_SCHEDULER_ADOPTED_SYMBOLS", ""),
            broker_unreachable_notify_enabled=os.getenv(
                "VINU_LIVE_BROKER_UNREACHABLE_NOTIFY_ENABLED", "true",
            ).lower() in ("1", "true", "yes"),
            broker_unreachable_renotify_cycles=int(os.getenv("VINU_LIVE_BROKER_UNREACHABLE_RENOTIFY_CYCLES", "6")),
            execution_fill_enrichment_enabled=os.getenv(
                "VINU_LIVE_EXECUTION_FILL_ENRICHMENT_ENABLED", "true",
            ).lower() in ("1", "true", "yes"),
            execution_fill_enrichment_batch=int(os.getenv("VINU_LIVE_EXECUTION_FILL_ENRICHMENT_BATCH", "25")),
            live_decision_feature_window_bars=int(
                os.getenv("VINU_LIVE_DECISION_FEATURE_WINDOW_BARS", "0"),
            ),
            live_decision_closed_bars_only=os.getenv(
                "VINU_LIVE_DECISION_CLOSED_BARS_ONLY", "false",
            ).lower() in ("1", "true", "yes"),
            live_decision_signal_outcomes_enabled=os.getenv(
                "VINU_LIVE_DECISION_SIGNAL_OUTCOMES_ENABLED", "true",
            ).lower() in ("1", "true", "yes"),
            live_decision_signal_horizon_bars=int(os.getenv("VINU_LIVE_DECISION_SIGNAL_HORIZON_BARS", "20")),
            live_decision_agent_timeout_sec=float(os.getenv("VINU_LIVE_DECISION_AGENT_TIMEOUT_SEC", "300")),
            live_decision_require_validated_strategy=os.getenv(
                "VINU_LIVE_DECISION_REQUIRE_VALIDATED_STRATEGY", "true",
            ).lower() in ("1", "true", "yes"),
            live_decision_novelty_enabled=os.getenv(
                "VINU_LIVE_DECISION_NOVELTY_ENABLED", "false",
            ).lower() in ("1", "true", "yes"),
            live_decision_novelty_ratio=float(os.getenv("VINU_LIVE_DECISION_NOVELTY_RATIO", "2.0")),
            live_decision_novelty_min_reference=int(os.getenv("VINU_LIVE_DECISION_NOVELTY_MIN_REFERENCE", "30")),
            live_decision_novelty_reference_rows=int(os.getenv("VINU_LIVE_DECISION_NOVELTY_REFERENCE_ROWS", "250")),
        )


def load_config() -> LiveConfig:
    return LiveConfig.from_env()
