# Full pipeline audit — findings (frozen, 2026-09-12)

Severity tiers: **CRITICAL** (a safety check can pass when it should have blocked,
or a live-trading path is fully blind to a real breach), **HIGH** (a real
correctness/data-integrity/duplicate-order risk), **MEDIUM** (a real but bounded
robustness or reporting-accuracy gap), **LOW** (minor / diagnostic-only impact).

Status column is updated in `fixes-log.md`, not here — this file is the frozen
as-found record.

## Pipeline 3: Live agent decision & execution (vinu-agent + vinu-live)

1. **CRITICAL** — `vinu-live/vinu_live/breaker/engine.py` `check_limits()` (daily-loss %,
   VaR, leverage, cluster exposure) only sets an in-memory `BreakerState.halted` flag
   local to that orchestrator. It never calls the persistent `/agent/broker/halt`
   endpoint that `OrderGuard.check()` actually reads via `is_trading_halted()`. The
   LLM-agent order path (`TradeTool` -> `OrderGuard`) has zero visibility into a
   portfolio-level breach detected by vinu-live's breaker.
2. **CRITICAL** — `vinu-agent/vinu_agent/broker/order_guard.py` `_fetch_risk_budget()`
   catches every exception from `GET /portfolio/risk/status` and returns `None`;
   `_check_risk_budget()` treats `None` as "check passed" (`GuardResult(True)`). A
   timeout/outage at the exact moment a symbol is at `TIER_HALT` silently un-blocks it.
3. **CRITICAL** — `vinu-portfolio/vinu_portfolio/risk_budget.py` `compute_risk_budget()`
   returns HTTP 200 with `aggregate.status="no_equity"` (not an error) when broker
   equity can't be read. `order_guard._check_risk_budget()` never inspects
   `aggregate.status`, only iterates the (now empty) `symbols` list, finds nothing,
   and approves.
4. **HIGH** — `order_guard.py` account fetch for `max_position_pct` /
   `max_capital_utilization_pct` (~line 323) and `_check_portfolio_concentration`
   (~line 646) each catch all exceptions and skip the check entirely on error.
5. **HIGH** — `audit/fact_audit.py` runs only after the whole agent turn finishes and
   only regex-scans the final prose against tool-result JSON; it never inspects
   `submit_order`'s actual arguments and cannot block or reverse an order that
   already executed earlier in the same turn.
6. **HIGH** — No symbol grounding before `OrderGuard`: `mandate.allowed_tickers`
   defaults to wildcard `{"*"}`; nothing checks the LLM's chosen symbol against the
   actual context under discussion.
7. **HIGH** — No idempotency key exposed to the LLM on the order tool
   (`trade_tool.py`'s JSON schema never exposes `client_order_id`, unlike vinu-live's
   own deterministic id). Submission timeouts are caught by a blanket `except
   Exception` reporting a generic error — a reasonable LLM retry after a timeout can
   become a real duplicate order.
8. **HIGH** — Reconciliation (`orchestrator.py` ~2240) only logs
   `alert_phantom_broker_position` when the broker holds a position the book has no
   record of; it never heals it.
9. **HIGH** — Negative `qty` + `reduce_only=True` bypasses OrderGuard's notional/
   position caps entirely: `trade_tool.py` never validates `qty > 0`, and
   `order_guard.py`'s fail-closed "cannot determine order value" guard is skipped
   when `reduce_only=True`, so a negative `qty` makes `value` negative and every
   `value > max_*` comparison trivially passes.
10. **MEDIUM** — `_check_symbol_override`, `_effective_limit`, `_check_active_artifact`,
    `_check_market_open` each independently fail open on their own store/DB/clock
    error; a single shared-infra hiccup can silently disable several layers at once.
11. **MEDIUM** — vinu-live's local `BreakerState` is a plain in-memory dataclass with
    no persistence/audit trail; a halt vanishes on process restart with no log.
12. **MEDIUM** — Fill-confirm/reconcile window can still double-fill: a network blip
    between vinu-live and vinu-agent (not the broker) drops the entry silently and
    retries next cycle with a fresh client-order-id.
13. **LOW** — Order-audit-log write happens after the kill-switch lock releases; if
    that write itself fails, only an `"order_executing"` trail remains for an order
    that did reach the broker, while the LLM sees a generic error (feeds into #7).

## Pipeline 4: Portfolio & risk state (vinu-portfolio + vinu-infra)

(Overlaps #2/#3 above — same root cause, listed once there.)

14. **HIGH** — `vinu-live/vinu_live/scheduler.py` `_fetch_positions()` swallows all
    exceptions/non-200s and returns `{}` without aborting the cycle (unlike
    `_fetch_portfolio`, which correctly aborts). `signal_translator.translate()`
    then treats `{}` as a genuinely flat book and sizes full-size orders instead of
    deltas.
15. **HIGH** — `vinu-live/vinu_live/trade_plan/orchestrator.py` (~941) reimplements
    the CVaR tail gate as a raw `cvar_95 > CVAR_THRESHOLD` instead of importing the
    shared, tested `risk_math.cvar_exceeds()`; `risk_bands.get("cvar_95_limit", 0.0)
    or 0.0` doesn't guard NaN (NaN is truthy, so `or 0.0` never fires).
16. **MEDIUM** — `vinu-infra/risk_math.py` `cvar_exceeds()` does `float(cvar_95) >
    float(threshold)`, which is `False` for NaN by construction — fails open on NaN
    if ever fed an unguarded source (not currently reachable given #15's upstream
    filtering, but the helper itself is unsafe).
17. **MEDIUM** — `vol_target_scale` / `forecast_confidence_scale` NaN-safety is
    accidental: relies on `min(1.0, nan) == 1.0` argument order; `min(nan, 1.0)`
    would return `nan` instead.
18. **MEDIUM** — vinu-portfolio's 60s `_portfolio_cache` can serve stale
    concentration/correlation data to `order_guard._check_portfolio_concentration`
    relative to a strategy activation change (equity/kill-switch checks are
    confirmed fresh — not cached).
19. **LOW** — `internal_auth_headers()` failures are swallowed silently in multiple
    call sites (`service.py`, `order_guard.py`, `client.py`), each with its own
    `try/except Exception: headers = None`; a broken auth setup looks identical to a
    network outage and folds into the fail-open behaviors above.

## Pipeline 1: Market data ingestion (vinu-stock-price + vinu-news + vinu-screener)

20. **CRITICAL** (reliability) — `vinu-stock-price/vinu_stock/cli.py` and
    `vinu-news/vinu_news/cli.py` live ingest `while True` loops have no exception
    handling around the core fetch/backfill/ingest calls (only an auxiliary
    `refresh_events` call is deliberately wrapped) — any unhandled exception kills
    the entire ingest worker process.
21. **HIGH** — `vinu-stock-price/vinu_stock/providers/alpaca.py` `_parse_bar_row`
    does direct `row["o"]/["h"]/["l"]/["c"]` indexing and `resp.json()` can raise
    `KeyError`/`ValueError`/`json.JSONDecodeError` — none of which are
    `requests.RequestException`, the only thing caught. Combined with #20 this
    crashes the whole worker on one malformed response.
22. **HIGH** — No OHLC/price sanity validation anywhere in the write path
    (`storage/models.py` `BarRecord.from_dict` blindly `float()`-casts); a bad tick
    is stored and trusted downstream with no bounds check.
23. **HIGH** — Cross-provider fallback can create duplicate-timestamp rows with
    different OHLC values: dedup key is `(symbol, provider, bar_ts)`, so a provider
    switch mid-stream leaves both providers' bars for the same minute as separate
    rows.
24. **HIGH** — Live/current-year data is excluded from gap detection entirely
    (`backfill/orchestrator.py` defaults `end_year = current_year - 1`); a mid-
    session provider outage leaves a real intraday gap that's never flagged.
25. **HIGH** — `backfill/orchestrator.py` `future.result()` (~289) has no
    try/except; one symbol's unhandled exception crashes the entire backfill run,
    which (via #20) crashes the whole ingest worker.
26. **MEDIUM** — `vinu-screener`'s `data_source.py` `get_ohlcv_batch` has a broad
    `except Exception: results = {}`, making a total API outage indistinguishable
    from "no data"; downstream labels every affected symbol `"insufficient_history"`
    (same bucket as legitimately thin symbols), and the scheduler completes the
    cycle cleanly with 0 fires instead of flagging degraded state.
27. **MEDIUM** — `vinu-news/.../price_reaction.py` `_close_at_or_after` has no
    upper bound on how far past `target_ts` it will search; a gap around the +1h/
    +1d mark silently returns a close from hours/days later, mislabeled as that
    reaction window.
28. **MEDIUM** — `integrations/stock_price.py` re-raises non-404 errors, so a
    transient vinu-stock-price hiccup 500s ticker/thread-detail reads instead of
    degrading gracefully.
29. **LOW** — `vinu-news/vinu_news/providers/alpaca.py` references `resp` inside
    `except requests.RequestException` before `resp` is ever assigned — a
    connection failure raises `NameError` inside the handler, destroying the real
    error from the logs (caught one level up, not fatal, but diagnosis-destroying).
30. **LOW** — `FeedPollResult.success` requires `article_count > 0`, so a healthy
    feed with zero new items is reported as `FAIL(None)`, muddying real outage
    signals.

## Pipeline 2: Research & backtest (vinu-research + vinu-simulator + vinu-strategy)

31. **HIGH** — `vinu-simulator/vinu_simulator/engine/custom_sim.py` (~55-61) catches
    any exception from a strategy's `generate_weights` (including a crash from
    insufficient history or a missing indicator column) with a bare
    `except Exception`, logs a WARNING, and silently replaces it with an all-zero
    weight series — the backtest completes as a normal `trade_count=0` result,
    indistinguishable from a legitimate no-trade decision.
32. **HIGH** — `vinu-simulator/vinu_simulator/clients/features_client.py`
    `get_indicators` swallows any fetch exception and returns `None`; the missing
    column is simply skipped from the merge, which can then trigger #31's silent
    zero-weight fallback if the strategy references it — two silent-failure layers
    stack.
33. **HIGH** — `vinu-research/vinu_research/loop.py`'s own walk-forward
    implementation (~1027, separate from the properly-guarded `walk_forward.py`)
    drops failed windows from `window_records` silently with no completeness/
    `n_planned` field, so a run where some windows failed looks identical to a full
    clean pass.
34. **HIGH** — That same `loop.py` walk-forward path (~981-1030) has no concurrency
    bound (unbounded `asyncio.gather`), unlike `walk_forward.py`'s explicit
    semaphore — increases odds of the timeout/exception-driven partial completion
    in #33.
35. **HIGH** — `vinu-simulator/vinu_simulator/engine/simulator.py` (~276-278) floors
    `nav_after` to `0.0` only in the *reported* equity curve; `cash`/`holdings` (the
    actual short position) are never liquidated, so a short that blew through zero
    equity can numerically "recover" later — a real margin call would have
    prevented this, and it distorts drawdown/CAGR for `allow_short=True` runs (the
    default).
36. **MEDIUM** — `comparison.py` passes `n_obs = equity_points - 1` straight into
    `deflated_sharpe_ratio`, whose only guard is `n_obs < 2` — a candidate with 2-3
    data points produces a confident-looking DSR that participates in scoring with
    no flag for the degenerate sample size.
37. **MEDIUM** — Inconsistent NaN handling for the same condition:
    `WeightSimulator.run` silently `continue`s on non-finite deviation;
    `SimulatorEnv.step` raises `ValueError` for the identical condition. The path
    actually used for research backtests is the silent one.
38. **MEDIUM** — `validation.py` `monte_carlo_permutation` uses the unseeded global
    `np.random.permutation`, while the rest of the engine is deliberately seeded via
    `config.random_seed` for reproducibility — an identical strategy/window can
    pass or fail this gate differently between runs.
39. **MEDIUM** — `metrics.py` reports Sortino/Calmar as `0.0` when there are zero
    losing days / zero drawdown, when the mathematically correct value is
    "undefined," not zero — a genuinely excellent no-downside strategy reads
    identically to a mediocre one.
40. **MEDIUM** — Fill-realism gap: volume is forward-filled across gaps, and
    `max_pct_of_volume` capping is skipped entirely when `vol == 0`; missing-volume
    impact cost is a flat, size-independent 0.5%.
41. **MEDIUM** — `loop.py` (~579-584) catches any exception from iteration 2+ of the
    research loop, logs a warning, and just truncates the loop, returning whatever
    `best_result` already existed as if the run completed normally.
42. **LOW-MEDIUM** — `WindowSplitter.split` silently returns `[]` for a too-short
    range; nothing distinguishes "walk-forward disabled" from "silently skipped for
    insufficient data."
43. **LOW** — `compute_full_metrics` converts every inf/-inf/NaN metric to `0.0` in
    one blanket pass with no per-field flag, so an honest `0.0` and an undefined
    metric are indistinguishable downstream.

**Checked and confirmed sound** (no fix needed): `sweep_grid.py` / `walk_forward.py`
bounded concurrency (correct semaphore usage, no shared-state races); T+1 execution
shift and position-sizer lookback gating (no look-ahead leakage found); malformed/
missing LLM tool-call args are caught before reaching `OrderGuard` or the broker;
`vinu_infra/retry.py`'s retry helpers are correctly defensive where they're actually
used.
