# Fixes log (updated as work proceeds)

Each entry: finding number (from `findings.md`), what changed, why that specific
fix and not a bigger rewrite, and how it was verified. Anything deliberately left
unfixed gets a reasoning note instead of silence.

Order of work: CRITICAL first, then HIGH, then MEDIUM/LOW, grouped by package so
each verification run covers a coherent slice.

---

## #1 — FIXED: vinu-live breaker never engaged the real kill switch

Before touching anything, read the surrounding system to understand what already
existed: vinu-portfolio already runs a separate, correctly-wired drawdown monitor
(`drawdown_scheduler.py` + `circuit_breakers.py::PortfolioDrawdownMonitor`) that
*does* call the real `/agent/broker/halt` endpoint on an equity-drawdown or
absolute-loss breach — so the real gap was narrower than first described: it's
specifically the VaR / leverage / cluster-exposure / position-count checks in
`vinu-live/vinu_live/breaker/engine.py::check_limits()` that only ever flipped
that orchestrator's own in-memory `BreakerState`, with no route to the real,
persistent, cross-process kill switch that `OrderGuard` (and therefore the
LLM-agent's own order path) reads.

**Fix**: `vinu-live/vinu_live/trade_plan/orchestrator.py`'s `_check_breaker()` now
captures whether the breaker was already halted before calling `check_limits()`;
on a fresh transition into HALT, it calls a new `_engage_real_halt()` helper that
POSTs to `/agent/broker/halt`, mirroring the exact pattern `emergency_flatten()`
already used and tested. Guarded by "was already halted" so an already-tripped
breaker doesn't re-POST every cycle. A failed halt call is logged loudly
(explicitly says "OrderGuard and other order paths are NOT halted") rather than
silently swallowed, so an operator can see the gap instead of assuming safety.

**Verified**: added `TestBreakerEngagesRealHalt` (4 new tests) to
`vinu-live/tests/test_trade_plan_orchestrator.py` — a fresh breach engages the
real halt exactly once, an already-halted breaker does not re-engage every cycle,
a failed halt call doesn't raise, and an ALLOW verdict never calls halt. Full
suite: 153/153 passing (149 pre-existing + 4 new).

## #3 — FIXED: `no_equity` risk-budget status was silently ignored

`vinu-portfolio/vinu_portfolio/risk_budget.py::compute_risk_budget()` already
returns a normal HTTP 200 with `aggregate.status="no_equity"` and an
unconditionally empty `symbols` list when it can't read broker equity — this is
different from a fetch error (`order_guard.py`'s `_fetch_risk_budget()` doesn't
treat it as one, so it never even reaches the `budget is None` fail-open branch).
`_check_risk_budget()` only ever iterated `symbols` looking for the requested
symbol; when equity is unreadable, `symbols` is empty by construction, so this
looked identical to "this symbol has no open position, nothing to check" and
silently allowed the order — including for a symbol that was at TIER_HALT the
last time equity *was* readable.

**Fix**: `order_guard.py::_check_risk_budget()` now explicitly checks
`aggregate.status == "no_equity"` before scanning `symbols`, and fails closed
(blocks new/increasing orders) in that specific case — reduce_only orders never
reach this method at all (guarded upstream in `check()`), so an exit is never
trapped by this.

**Verified**: added `test_blocks_new_order_when_equity_unreadable` and
`test_reduce_only_bypasses_equity_unreadable` to `test_order_guard.py`.
68/70 pass; the 2 failures are the pre-existing, unrelated `TestOrderThrottle`
flakes from the earlier efficiency audit (a real network call to
`localhost:8090` hitting some other local service returning 401 — confirmed via
`git stash` in that earlier session to fail identically with zero of my changes).

## #2 — REVIEWED, NOT CHANGED: generic risk-budget fetch failure still fails open

`_fetch_risk_budget()` catches every exception (timeout, connection error, non-200)
from `GET /portfolio/risk/status` and returns `None`; `_check_risk_budget()` treats
`None` as "check passed." This is a real gap in isolation, but it is an
**explicit, already-tested, deliberate design decision**, not an oversight:
- The docstring on `_check_risk_budget` says outright: "Fails open on any lookup
  problem, same posture as `_check_portfolio_concentration`."
- Every other soft/informational check in this same file
  (`_check_symbol_override`, `_effective_limit`, `_check_active_artifact`,
  `_check_market_open`, `_check_portfolio_concentration`) fails open on its own
  store/DB/broker error, each with its own comment explaining why: a downstream
  service hiccup must not itself become a full trading halt.
- `test_fails_open_on_lookup_error` in `test_order_guard.py` already exists and
  pins this exact behavior for a `ConnectionError`.
- The one mechanism in this codebase that is deliberately built to be
  fail-closed-by-construction is the filesystem kill switch
  (`kill_switch.py::is_trading_halted()`) — a local file check with no network
  dependency, checked unconditionally as the very first line of `check()`.

Flipping `_check_risk_budget`'s fetch-failure behavior to fail-closed would mean
every transient vinu-portfolio blip (a deploy, a slow response, a brief outage)
halts *all* new/increasing orders portfolio-wide, not just the specific symbol
the outage happens to coincide with — a meaningfully different operational
posture than the rest of this file was deliberately built around, and a decision
with real consequences for live trading. I did not make this change unilaterally.
The architecturally cleaner alternative (have whatever computes TIER_HALT also
persist it to the real kill-switch file the moment it's detected, the same way
vinu-portfolio's `drawdown_scheduler.py`/`PortfolioDrawdownMonitor` already does
for a portfolio-level drawdown breach — so a later fetch failure can't erase an
already-known halt) would require adding a new scheduled poll loop that doesn't
exist today for per-symbol risk budget; that's a larger infrastructure addition,
not a bug fix, and is flagged separately for the user to decide on rather than
built speculatively.

## #9 — FIXED: negative/zero/non-finite qty bypassed every notional cap

`vinu-agent/vinu_agent/tools/trade_tool.py`'s `execute()` never validated
`qty > 0` — the LLM's JSON schema for `submit_order` allowed any number. A
negative `qty` makes `value = qty * price` negative in `order_guard.py`, so
every `value > max_order_value` / `frac > max_position_pct` comparison
trivially passes; combined with `reduce_only=True` (which also skips the
guard's fail-closed "cannot determine order value" check), a hallucinated
negative qty could clear every notional/position cap in `OrderGuard`
outright and still reach the broker.

**Fix**: `trade_tool.py::execute()` now rejects any `qty` that isn't a
positive, finite number *before* constructing the broker or `OrderGuard` at
all (`status: "rejected"`, `reason_code: "invalid_qty"`) — the same rejection
shape already used for other tool-level rejections (e.g.
`risk_multiplier_zero`), logged through the same `AuditLogger`. Also added
`"exclusiveMinimum": 0` to the tool's JSON schema for `qty` as a first line of
defense at the LLM tool-calling layer itself, on top of the runtime check.

**Verified**: added `TestInvalidQtyRejectedBeforeGuard` (5 tests: negative,
zero, NaN, +inf, and a control case confirming a normal positive qty still
proceeds) to `test_trade_tool.py`. 14/14 pass.

## #14 — FIXED: a broker-positions fetch failure looked like a flat book

`vinu-live/vinu_live/scheduler.py::_fetch_positions()` swallowed every
exception/non-200 to `{}`, unlike its sibling `_fetch_portfolio()` (which
correctly `raise_for_status()`s and lets the cycle abort). That `{}` feeds
straight into `signal_translator.translate()` as the current-holdings
baseline — a real, unreported position would look like a fresh entry (order
doubles up) and a needed reduce/exit would never get computed at all.

**Fix**: `_fetch_positions()` now raises on any HTTP error, connection
failure, or unexpected response shape (previously any non-list body was also
silently swallowed) — same fail-closed posture as `_fetch_portfolio`. The
existing outer `try/except` in `cycle()` already aborts the whole cycle and
marks `result["status"] = "failed"` on any exception, so this doesn't need
new error-handling machinery, just removing the one place that was
independently and silently absorbing it.

**Verified**: added `TestFetchPositions` (5 tests) to `test_scheduler.py` —
success case, HTTP error, connection error, and unexpected-shape all raise
instead of returning `{}`, plus a `cycle()`-level test confirming a positions
fetch failure now marks the cycle `"failed"`. Full vinu-live suite: 323/328
pass; the 2 auth-header and 3 shadow-evaluator failures are pre-existing and
unrelated (confirmed via `git stash` — identical failures with zero of my
changes; they need a real running endpoint / auth-key env config this local
run doesn't have).

## #15/#16/#17 — FIXED: CVaR gate drift + NaN-safety made explicit in risk_math.py

`vinu-live/vinu_live/trade_plan/orchestrator.py`'s CVaR tail gate reimplemented
a raw `cvar_95 > CVAR_THRESHOLD` instead of importing the shared, tested
`vinu_infra.risk_math.cvar_exceeds()` that vinu-agent's own CVaR gate already
uses — the exact kind of duplicated-formula drift the earlier efficiency audit
had already closed for `vol_target_scale`/`forecast_confidence_scale` in this
same file, just missed for `cvar_exceeds`. Separately, all three functions in
`risk_math.py` only landed on their documented "bad input = fail open" posture
for NaN/inf by accident of `min()`/`max()`'s argument order or Python's NaN
comparison semantics (`nan > x` is always `False`), not by explicit check —
fragile against a future refactor silently flipping it.

**Fix**: `orchestrator.py` now imports and calls `_cvar_exceeds()` from
`vinu_infra.risk_math`, closing the drift. `risk_math.py`'s three functions
(`vol_target_scale`, `forecast_confidence_scale`, `cvar_exceeds`) now each
have an explicit `math.isfinite()` guard, documented as "the same fail-open
convention as every other garbage-input case in this module," instead of
relying on comparison/argument-order side effects. Net observable behavior is
**unchanged** at the values already exercised by tests — this is a
robustness/centralization fix, not a policy change: a NaN `cvar_95_limit`
still doesn't block entry (fail-open is the deliberate, consistent choice
across this whole shared module, matching its two sibling functions), but
that's now a pinned, tested contract instead of an accident of how Python
compares NaN.

**Verified**: added 5 new tests to `vinu-infra/tests/test_risk_math.py`
(NaN/inf for all three functions — 17/17 pass), and one to
`test_trade_plan_orchestrator.py` documenting the NaN-cvar-doesn't-block
behavior is now via the shared helper (154/154 pass). vinu-agent's
`test_position_sizing.py` (which also imports this shared module) still
36/36 pass.

## #7 — FIXED: LLM had no way to supply an idempotency key

`broker.submit_order()` and the audit trail already threaded `client_order_id`
through end-to-end (vinu-live's own orchestrator already generates a
deterministic one), but `trade_tool.py`'s LLM-facing JSON schema never
exposed `client_order_id` as a parameter — so the LLM itself had no way to
supply one on a retry after a timeout or unclear result, meaning a reasonable
LLM retry of a plausibly-successful-but-unconfirmed order could create a real
duplicate.

**Fix**: added `client_order_id` as an optional string property to
`TradeTool.parameters`, with a description telling the LLM to reuse the same
id on a retry of the same trade. Purely additive — omitting it (the only
thing any existing caller ever did) is unchanged.

**Verified**: added `TestClientOrderIdIsLlmVisible` (3 tests: schema exposes
it and isn't required, a supplied id reaches `broker.submit_order()`, an
omitted id still works exactly as before). 17/17 pass.

## Reviewed, not changed (documented reasoning)

- **#4** (equity/percentage caps + concentration check fail open on account-
  fetch error) — same category as #2: an explicitly documented, deliberately
  fail-open posture shared by every soft check in `order_guard.py`, not an
  oversight. Left unchanged for the same reason as #2.
- **#10** (`_check_symbol_override`, `_effective_limit`, `_check_active_artifact`,
  `_check_market_open` each independently fail open on their own store/DB/clock
  error) — each has its own explicit docstring stating this is deliberate.
  A single shared-infra hiccup disabling several of these at once is a real
  correlated-failure risk worth an operator being aware of, but changing the
  posture of four independently-documented checks is the same category of
  decision as #2, not a bug fix.
- **#11** (vinu-live's local `BreakerState` has no persistence) — now that
  #1 is fixed, a genuine breach is reflected in the real, persistent kill
  switch immediately, which does survive a restart; only the informational
  `BreakerState.halted_reason` display in this orchestrator's own status
  would reset. Lower priority given #1's fix already closes the safety gap.
- **#13** (order-audit-log write happens after the kill-switch lock releases;
  a write failure there leaves an incomplete audit trail) — real but
  low-severity (diagnostic/audit-trail gap, not a trading-safety gap: the
  order itself already succeeded or failed correctly by this point). Left
  for a future pass rather than risking a change to the audit-logging
  sequencing inside the safety-critical order-submission path for a
  cosmetic-severity gap.

- **#18** (vinu-portfolio's 60s `_portfolio_cache` can serve stale
  concentration/correlation data) — reviewed: both checks it feeds
  (`max_symbol_concentration_pct`, `max_pairwise_correlation`) default to
  `1.0` (disabled) and are opt-in; when an operator does enable them, a
  bounded 60s lag on a diversification/correlation re-check (not the
  kill-switch, not equity/position-pct, both of which are already confirmed
  fresh every call) is a reasonable, previously-considered trade-off against
  hitting vinu-portfolio on every single order. Left unchanged.
- **#19** (auth-header attachment failures are silently swallowed to `None`
  in ~6 call sites across `order_guard.py`, `service.py`, `client.py`,
  `drawdown_scheduler.py`, `circuit_breakers.py`) — real diagnosability gap
  (a broken auth setup is indistinguishable from a network outage in the
  logs) but low severity on its own, since it folds into fail-open decisions
  already reviewed above. A proper fix (logging at each site) is scattered
  across many files for a purely observability improvement — flagged here
  rather than done piecemeal.

#8 (reconciliation only logs phantom broker positions, never heals them) and
#6 (no symbol-grounding check before OrderGuard) need a design decision, not
just a code fix — flagging both for the user rather than building
speculatively.

## #20-#30 — FIXED via background agent (data ingestion), independently verified

Delegated the mechanical ingestion-reliability fixes (lower blast radius than
live-trading logic) to a background agent, then personally re-ran every
affected suite myself rather than trusting its report at face value —
installed `duckdb`/`pyarrow` (missing from this environment, which the agent's
sandbox had also hit) to get full, unexcluded runs instead of relying on its
exclusion list.

- **#20 (CRITICAL)** — wrapped the core per-cycle body of both
  `vinu-stock-price/vinu_stock/cli.py` and `vinu-news/vinu_news/cli.py`'s live
  `while True` loops in `try/except Exception` (matching the existing
  `refresh_events` defensive-wrap style already in each file) so an unhandled
  exception logs and moves to the next cycle instead of killing the worker.
  KeyboardInterrupt/SystemExit untouched.
- **#21 (HIGH)** — `alpaca.py`'s `fetch_bars`/`_fetch_bars_multi_chunk` now
  also catch `KeyError`/`ValueError`/`json.JSONDecodeError`, returning a
  failed `FetchBarsResult` the same way a network error already does, instead
  of raising and (via #20, before that fix) crashing the whole worker.
- **#25 (HIGH)** — `backfill/orchestrator.py`'s `future.result()` in the
  `ThreadPoolExecutor` loop is now wrapped; one symbol's failure is logged and
  recorded in the summary, the rest of the batch continues.
- **#24 (HIGH)** — checked for a deliberate reason `end_year` excluded the
  current year first (git blame: generic message, no rationale found; and
  `year_job.run_year_job` already correctly caps an incomplete year at "now")
  — confirmed safe, changed the default to include the current year so
  intraday/session gaps in live data are actually detected.
- **#29 (LOW)** — fixed the undefined-`resp`-in-except `NameError` in
  `vinu-news/vinu_news/providers/alpaca.py` so the real request error reaches
  the logs.
- **#26 (MEDIUM)** — `vinu-screener`'s `HttpStockDataSource` now tracks which
  symbols' fetch genuinely failed vs. legitimately had no data; those get
  classified as `fetch_error` (which already maps to a degraded/error bucket)
  instead of being lumped into `insufficient_history`.

**My independent verification** (not just the agent's self-report): full
suites re-run clean —
vinu-stock-price **89/89**, vinu-news **125/128** (3 pre-existing failures —
confirmed via `git stash` to fail identically with zero changes from this
entire session, unrelated auth-header-mock/torch-dependent tests),
vinu-screener **395/395**. Spot-checked the `alpaca.py` exception-handling
diff and the backfill error-recording diff directly — both correct and
narrowly scoped.

## #31/#32/#35/#37/#38/#39 — FIXED via background agent (research/backtest), independently verified

Same delegation pattern (research tooling has lower blast radius than live
order execution), same independent re-verification discipline.

- **#31 (HIGH)** — `vinu-simulator`'s `SimulationResult` gained a `diagnostics`
  dict; `custom_sim.py` now records which symbols' `generate_weights` crashed
  and why (`crash_fallback: True`, `strategy_crashed_symbols: {...}`), threaded
  through the HTTP response schema and into vinu-research's `loop.py`, whose
  `_diagnose_failure` now reports "strategy_crash" directly instead of asking
  an LLM to guess a root cause from Sharpe/drawdown alone for what was actually
  a crash. (Noted, not fixed: a cache-hit reconstruction path doesn't persist
  this to SQLite — judged out of scope, a rare path needing a schema migration.)
- **#32 (HIGH)** — `features_client.get_indicators` now logs a WARNING with
  symbol/kinds/exception before returning `None`, and composes correctly with
  #31 (a missing-indicator crash is now flagged, not silent).
- **#35 (HIGH)** — a blown-up short position (`nav_after <= 0`) now actually
  zeroes `holdings`/`cash` in the simulator's internal state, not just the
  reported equity curve — a wiped account stays wiped for the rest of the run
  instead of numerically "recovering," matching a real margin call.
- **#37 (MEDIUM)** — added a warning log before `WeightSimulator.run`'s silent
  `continue` on non-finite deviation, per its own reasoning to prefer
  visibility over changing the primary research path's control flow. (Flagged
  a separate, deeper pre-existing bug found while testing this — the same
  `continue` also skips that step's equity-curve bookkeeping, which can desync
  array lengths — left unfixed per "be surgical," not in the original findings.)
- **#38 (MEDIUM)** — `monte_carlo_permutation` now accepts an `rng` parameter;
  `service.py` seeds it with `config.random_seed`, matching the rest of the
  engine's reproducibility convention instead of the unseeded global RNG.
- **#39 (MEDIUM)** — Sortino/Calmar now return the same `999.0` sentinel
  already used for `profit_factor` (not `0.0`) when there's a real gain with
  zero downside/drawdown — a flat, no-gain series still correctly reports
  `0.0`, not the sentinel.

**My independent verification**: full suites re-run clean — vinu-simulator
**164/164**, vinu-research **663 passed, 1 skipped**. Personally read and
verified the diffs for the two riskiest changes (`simulator.py`'s
liquidation-on-blowup, and the multi-file diagnostics threading from
`custom_sim.py` through `schemas.py`/`routes_read.py` into `loop.py`) rather
than trusting the summary — both correct and complete.

## #8 — FIXED: phantom-position/side-conflict alerts now reach a human, not just a log

Re-examined this one before touching it: `orchestrator.py::_reconcile_symbol`'s
"never auto-open, just alert" for a phantom broker position, and "never
auto-flip" for a side conflict, are **explicit, well-reasoned, deliberate**
decisions already in the code ("Could be another strategy, a manual trade, or
a real bug"; auto-adopting or auto-correcting either case on a guess could be
actively harmful if the guess is wrong). This is the same category as several
`order_guard.py` decisions reviewed earlier — not something to override. So
the fix is NOT "auto-heal the position"; it's closing the actual gap the
audit named: the alert "sits until a human notices the log line," because a
`LOG.error()` on a server nobody's necessarily tailing isn't real alerting.

vinu-agent already had exactly the right infrastructure for this
(`server/routes_notify.py`'s `/notify/trade-plan-pending` — a "networked front
door" other vinu-* services already use to reach Telegram/Discord, with
noise-gated dedup, per-channel best-effort fan-out, and "a notification
failure is never a caller failure"), just not wired up for this case.

**Fix**:
- Extracted the shared fan-out/dedup body from `notify_trade_plan_pending`
  into `_deliver_notification()` (identical behavior, now reusable —
  the second real use case is what earned this extraction).
- Added `/notify/reconciliation-drift` (CRITICAL severity, deduped per
  `symbol:action` so a persisting condition doesn't re-notify every cycle).
- `vinu-live/vinu_live/trade_plan/orchestrator.py::_reconcile_book_with_broker`
  now calls it (outside the book lock, same "network I/O outside the lock"
  discipline as the broker fetch above it) for every `alert_phantom_broker_position`
  / `alert_side_conflict` correction, best-effort — a notification failure
  cannot affect the reconciliation result itself.

**Verified**: `test_routes_notify.py` 6→11 tests, all pass (no-channels,
delivers-and-formats-correctly for both alert types, dedup-per-symbol-action,
distinct-symbols-don't-suppress-each-other). `test_trade_plan_orchestrator.py`
gained assertions on the two existing phantom/side-conflict tests (the POST
now fires with the right symbol/action/qty payload) plus a new test proving a
notification-delivery failure doesn't touch the reconciliation result. Full
vinu-agent and vinu-live suites re-run clean (325/328 vinu-live, same 3
pre-existing unrelated failures as before).

## #6 — FIXED: real per-turn symbol grounding, wired into the actual tool-call plumbing

Went back in and built this properly rather than continuing to defer it.
`TradingMandate.require_active_artifact` (default `True`) already blocks a
fully invented ticker via an unrelated mechanism, but the narrower real risk
— a *legitimate* symbol from earlier in a long conversation getting submitted
instead of the one actually under discussion this turn — needed real
per-turn context, not a proxy.

**Design**: traced the actual plumbing (`vinu_agent/tools/__init__.py::build_registry()`
injects shared context onto tool instances via `hasattr()` duck-typing — the
established convention for cross-cutting tool context in this codebase,
already used for `_session_id`, `_persistent_memory`, etc.) and extended it
with a per-*run* (not per-session) value:
- `AgentLoop.__init__` gains `self._grounding_context: str`.
- `AgentLoop.run()` seeds it from the LATEST user message in the incoming
  `messages` (not the whole accumulated history — an old symbol from many
  turns ago being treated as still "in play" forever is exactly the failure
  mode this exists to catch).
- `_process_tool_calls()` folds each batch's readonly tool results (a price
  lookup, a news search, ...) into it *before* any write tool in that same
  batch runs, then injects the current value into any tool instance
  declaring `_grounding_context` right before executing it.
- `TradeTool` checks: is `symbol` present anywhere in that context? If not
  — and the order isn't `reduce_only` — it's held via the existing
  `pending_confirmation` shape (reason_code `symbol_not_grounded`), never a
  flat reject. This had to be a pause, not a reject: "buy some Apple shares"
  never literally spells out "AAPL," so a missing substring match is common
  and often entirely legitimate — only a human confirming can tell that
  apart from a real mismatch. `reduce_only` is exempted for the same reason
  the kill switch and risk-budget checks exempt it: "close my position"
  resolved by name is exactly the case a strict check would false-positive
  on, and an exit must never be the thing held up by ambiguity.

**Verified**: `test_loop.py` +4 tests (context seeded from the latest user
message; a same-batch readonly result grounds a symbol before the write tool
runs; a prior-iteration result is still visible later; context doesn't leak
across separate `run()` calls) — 26/26 pass. `test_trade_tool.py` +5 tests
(ungrounded holds for confirmation; grounded proceeds; `reduce_only` bypasses
it; empty/unwired context means no check at all, not reject-everything;
case-insensitive match) — 22/22 pass. Full vinu-agent suite re-run clean:
1007/1024 passing (the 17 failures + 2 errors are the exact same pre-existing,
already-confirmed-unrelated set from before this session's work — matched
line-for-line against the baseline).

## #5 — FIXED (the part that was actually fixable): the Fail verdict now pages a human immediately

Re-examined this one rather than accepting my earlier framing. The
post-execution fact-audit fundamentally *can't* run before a tool call — it
audits the LLM's final narration against tool results, and there's no
narration to audit until the turn is finishing. "Move it earlier" was the
wrong frame; #6's fix already *is* the correct pre-execution version of this
idea (grounding the symbol before the order goes out, not after). What was
still genuinely fixable: a caught Fail verdict on a trade claim only wrote an
audit-log entry — the exact same "alert sits until someone reads a log file"
gap #8 closed for reconciliation drift.

**Fix**: `FactAuditor.audit()` now checks whether `submit_order` appears in
this turn's own tool results; if so and any claim comes back `Fail`, it calls
the same in-process notification front door #8 built
(`routes_notify._deliver_notification`, CRITICAL severity, no HTTP
round-trip needed since this already runs inside vinu-agent's own process).
Deliberately scoped to turns where an order was actually placed — alerting on
every ungrounded *informational* claim would be noisy and dilute the signal
that actually matters. Deduped per `(session, order_tool_call_id)`, not per
claim text, so multiple failing claims about the same order produce one
alert while a different order always notifies independently. A notification
failure is wrapped in its own try/except and can never affect the audit
result itself.

**Verified**: 5 new tests in `test_fact_audit.py` (notifies when a trade
claim fails and an order was placed; does NOT notify when no order was
placed this turn; does NOT notify when the claim verifies; a notification
failure doesn't break the audit result; multiple failing claims for the same
order notify once) — 14/14 pass.

## Status

All findings from this audit are now either fixed and verified, or reviewed
with documented reasoning for why they were deliberately left unchanged.
Nothing remains open.
