# Live-behavior flags added by the inconsistencies-v2 work (all default OFF unless stated)

Everything below ships switched off. Nothing in the repo turns any of it on. A flag is switched on per service by setting its environment variable (for the
docker setup, in that service's environment block). Each row links to the section of `04-implementation-status.md` with the full limits.

Read the "Can newly stop trading?" column before turning anything on: those flags can make the system trade less or halt, which is the point, but you
should expect it.

## vinu-live (hourly scheduler path unless noted)

| Flag (env var) | Fixes | What it changes when on | Can newly stop trading? | Turn on when |
|---|---|---|---|---|
| `abort_on_equity_read_failure` (`VINU_LIVE_ABORT_ON_EQUITY_READ_FAILURE`) | A7 | A failed read of a configured broker's equity aborts the cycle instead of sizing on a $1,000,000 placeholder | Yes: a flaky account read skips that hour | You are on a configured Alpaca account |
| `scheduler_exits_exempt_from_halts` (`VINU_LIVE_SCHEDULER_EXITS_EXEMPT_FROM_HALTS`) | A5 | Reducing orders are tagged `reduce_only`, go as market orders, and pass the breaker halt, kill switch and spread / earnings gates; increases are gated as before | No (it lets sells through) | Before real money; pair with the two flags below |
| `scheduler_use_daily_allocation` (`VINU_LIVE_SCHEDULER_USE_DAILY_ALLOCATION`) | A1 | Sizes from `/portfolio/daily-allocation` scaled by deployable / account equity (drawdown halve / flat, maturity ladder, reserve, tilts); falls back to `/portfolio/state` on failure | Yes: "flat" now sells the portfolio down | Before real money, with the exits flag on |
| `scheduler_respect_trade_plan_symbols` (`VINU_LIVE_SCHEDULER_RESPECT_TRADE_PLAN_SYMBOLS`) + `scheduler_adopted_symbols` (`VINU_LIVE_SCHEDULER_ADOPTED_SYMBOLS`) | A2 | Orchestrator-owned symbols (open book position or ACTIVE plan) are neither targeted nor traded by the scheduler; a held position nothing targets any more is closed **only if the scheduler opened it** (order ledger, or the adopted list); hand-placed holdings are never touched; unknown ownership closes nothing | Yes, for those symbols only | Before real money |
| `scheduler_breaker_uses_broker_account` (`VINU_LIVE_SCHEDULER_BREAKER_USES_BROKER_ACCOUNT`) | A6 | Breaker checks the broker's positions and an equity-based daily loss (incl. unrealized) | Yes: >20 positions, >2x leverage or -5% on the day now halts | Before real money |
| `scheduler_entry_guards_enabled` (`VINU_LIVE_SCHEDULER_ENTRY_GUARDS_ENABLED`) | A4 (earlier) | Cooldown, stale-data and turbulence guards on new exposure (entries only) | Yes, for entries | Before real money |
| per-symbol loss lockout: `VINU_LIVE_SYMBOL_LOCKOUT_LOSSES` (N; 0 = off) + `VINU_LIVE_SYMBOL_LOCKOUT_HOURS` (72) | v1 C1 | A symbol whose last N closed trades all lost is locked for new entries (orchestrator, and the scheduler's entry guards if on); a win resets it; exits never blocked; `GET /live/lockouts` | Yes, for that symbol's entries | After a few weeks of paper data show how often it would fire |
| `precondition_enforcing_enabled` (`VINU_LIVE_PRECONDITION_ENFORCING_ENABLED`) | v1 A8 | No position is opened for a live-decision EXECUTE whose `precondition_held` is False | Yes, for those decisions | When you trust the agent's precondition flag |
| `live_decision_feature_window_bars` (`VINU_LIVE_DECISION_FEATURE_WINDOW_BARS`, a number; 0 = off) | A8 | Live poller computes features on that many bars (recommend 600) so EMA-100/200 match backtest | No (changes when conditions fire) | Before relying on EMA-100/200 in must-conditions |
| `VINU_MODEL_SERVICE_URL` (initial-analysis, news; set by compose) | models | Model angles and FinBERT run in `models-api`; unset = in-process (needs torch) | No (same results, different place) | Already set in compose |
| `VINU_MODELS_ALLOW_PROXY` (models-api, default true) | models | false = an angle that fell back to its proxy forecast becomes a 503 / error run instead of a stored proxy row | Yes (fewer rows when a model cannot load) | After weights are in `data/models` and you want no proxy rows at all |
| `VINU_MODELS_MAX_CONCURRENT` (1), `VINU_MODELS_TIMEOUT_SEC` (600) (models-api) | models | One inference at a time on the GPU; per-request time limit | No | Raise the timeout if a trained angle on a long history needs more |
| `live_decision_closed_bars_only` (`VINU_LIVE_DECISION_CLOSED_BARS_ONLY`) | audit S2 | Poller asks vinu-stock-price for closed bars only, so it never decides on a still-forming candle | Yes, by one candle (decisions wait for the bar to end) | After the S1 fix is deployed and you want strict candle-close decisions |
| `live_decision_novelty_enabled` (`VINU_LIVE_DECISION_NOVELTY_ENABLED`; also `_RATIO` 2.0, `_MIN_REFERENCE` 30, `_REFERENCE_ROWS` 250) | B1 | Compares each new candle's live features with that ticker's own recorded snapshot history; logs, stores a `live_novelty` row, and tells the live-decision agent to prefer SKIP when the ratio is high | No (observe-only; only adds a caution line to the agent's task) | Any time; watch `live_decision.input_novelty->live.poller` and the ratios for a week before trusting the 2.0 threshold |
| `live_decision_stop_pct` / `live_decision_max_hold_bars` (per strategy; 0 = off) | A3 (earlier) | Rule-based stop and maximum hold for live-decision positions | No (it closes positions) | Per strategy, when you want an exit rule |
| `live_decision_max_trigger_attempts` (`VINU_LIVE_DECISION_MAX_TRIGGER_ATTEMPTS`, default 3; 0 = old) | v1 C1 (earlier) | **ON by default**: stuck live-decision triggers are retried on later candles then expired with a notification | No | Already on |
| `execution_log_enabled` (`VINU_LIVE_EXECUTION_LOG_ENABLED`, **default ON**) | Phase 5.4 | Ledger of every scheduler order slice (reference price, spread, order type, broker answer) in `execution_log.db`, read at `GET /live/executions`; log-only | No | Already on |
| `broker_unreachable_notify_enabled` (`VINU_LIVE_BROKER_UNREACHABLE_NOTIFY_ENABLED`, **default ON**) + `broker_unreachable_renotify_cycles` (`VINU_LIVE_BROKER_UNREACHABLE_RENOTIFY_CYCLES`, 6) | loud failure | CRITICAL notification when the broker cannot be read (first bad cycle, reminder every N, one recovery message); notification only | No | Already on |
| `execution_fill_enrichment_enabled` (`VINU_LIVE_EXECUTION_FILL_ENRICHMENT_ENABLED`, **default ON**) + `execution_fill_enrichment_batch` (`VINU_LIVE_EXECUTION_FILL_ENRICHMENT_BATCH`, 25) | Phase 5.5 | Each cycle, look up recent accepted orders at the broker and record fill price and slippage in the ledger; read-only toward the broker | No | Already on |

## vinu-research

| Flag (env var) | Fixes | What it changes when on | Turn on when |
|---|---|---|---|
| `confidence_reliability_log_enabled` (`VINU_RESEARCH_CONFIDENCE_RELIABILITY_LOG_ENABLED`, **default ON**) | B1 | One raw-vs-calibrated confidence line on each new plan; no score change | Already on |
| `calibrated_confidence_in_ev_enabled` (`VINU_RESEARCH_CALIBRATED_CONFIDENCE_IN_EV_ENABLED`) | B1 | Trade Score EV term uses the calibrated confidence | After at least a few hundred closed trades exist |
| `confluence_excludes_forecast_confidence` (`VINU_RESEARCH_CONFLUENCE_EXCLUDES_FORECAST_CONFIDENCE`) | B1 | Drops the duplicate `forecast_confidence` vote from the confluence ledger | When you accept the score scale shifting |
| `forecast_prompt_extra_context_enabled` (`VINU_RESEARCH_FORECAST_PROMPT_EXTRA_CONTEXT_ENABLED`) | v1 B3 (earlier) | Forecast LLM sees the regime and options-implied move | When you want to test whether it helps |
| `refine_prompt_full_metrics_enabled` (`VINU_RESEARCH_REFINE_PROMPT_FULL_METRICS_ENABLED`) | v1 B4 (earlier) | Refinement LLM sees the full metric row | Same |

## Not flags (always on, fail-closed or read-only)

- Plan approval refuses a scored plan with no computed risk band (`risk_not_computed`; `force` + `approver` overrides) -- B2.
- Pipeline edge manifest + runtime recorder, `GET /research/pipeline-edges` -- read-only.
- Look-ahead / warmup-drift checks (`vinu-tools`), sweep code hashes, run-quality metadata, allocation-history routes -- read-only / additive.

## A suggested order for real money (your call)

1. `scheduler_exits_exempt_from_halts` and `abort_on_equity_read_failure` first: they only let sells through or stop on a bad read.
2. Then `scheduler_breaker_uses_broker_account` and `scheduler_entry_guards_enabled`: they add stops. Watch a few days of paper for false halts.
3. Then `scheduler_use_daily_allocation` (+ `scheduler_respect_trade_plan_symbols` if both executors run): they change sizing.
4. `live_decision_feature_window_bars=600` and `precondition_enforcing_enabled` when you are ready for the live-decision path to behave differently.
5. `live_decision_novelty_enabled` can go on at any point: it only observes and adds a caution to the agent's task.
