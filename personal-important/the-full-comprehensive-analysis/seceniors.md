# VINA REAL-WORLD SCENARIO STRESS TEST — COVERAGE MATRIX (COMPLETE)

Reconstructed and completed from `session-ses_f7bf.md`, which was cut off twice by the
model's output limit (mid-Scenario-18, and mid-Section-C of the summary). All 36 scenario
tables below are unedited from that session. Sections C–F of the summary are completed here
for the first time, based on the same 36-scenario evidence.

Source implementation: `/home/somic_cps/Vina/my-trading-work-3/vinu-components/`
Source gap docs: `/home/somic_cps/Vina/my-trading-work-3/questions -answers/gaps-implementation/`

## VERIFICATION AUDIT (2026-09-09)

All 36 scenarios below were re-checked against the current `vinu-components` source
(not the docs) after the original stress-test session. The repo has moved since that
session was written — several gaps have genuinely been closed. Each scenario's table
now carries a **Verified** line stating the current on-code status.

### ✅ RESOLVED since the original analysis (6 of 36)

| # | Scenario | Fix found in code | My rating |
|---|----------|--------------------|-----------|
| 4 | Volatility increase mid-trade / no default trailing / no time-stop | `orchestrator.py`: unconditional 2×ATR trailing stop (`trailing_stop_for`, runs regardless of whether the plan defines a trailing contingency) + `max_hold_days` time-stop that force-exits via `_apply_invalidation`. Both marked "(15 step2)" in comments. | **9/10** — both named gaps closed with real, unconditional logic. Doesn't add vol-*regime* awareness beyond ATR itself, so still not a perfect fix, but functionally solves the scenario. |
| 7 | Revenge trading — no cooldown after losses | `orchestrator.py:52-104`: `COOLDOWN_LOSSES=2` / `COOLDOWN_HOURS=24` — 2 consecutive losses locks new entries on that symbol for 24h; exits explicitly exempted ("Exits never blocked"). This is exactly the Freqtrade-style fix the original analysis asked for. | **9/10** — textbook fix, configurable via env, exits correctly excluded. |
| 17 | No CVaR gate / no dynamic vol targeting | `vinu-agent/vinu_agent/agent/position_sizing.py`: `cvar_exceeds()` blocks sizing to 0 when CVaR95 > threshold; `vol_target_scale()` scales size by `target_vol/current_vol`. Wired into the real order path via `risk_gatekeeper_hook.py`, not just a standalone tool. | **6/10** — correctly built and wired, **but `VINU_RISK_CVAR_ENABLED` and `VINU_RISK_VOL_TARGET_ENABLED` both default to `false`.** The code is production-ready; it's just switched off. This is the highest-value one-line change you can make today. |
| 27 | No idempotency keys — double-fill risk | `orchestrator.py:777-792`: every order gets a `client_order_id` = `artifact+symbol+side+qty+minute-bucket`, gated by `VINU_EXEC_IDEMPOTENCY_ENABLED` (defaults **on**). Retry within the same minute dedupes on the broker. | **8/10** — real fix, on by default. Minute-bucket granularity means a retry >60s later could still double-fill, but that's an edge case, not the common retry-storm failure mode. |
| 28 | Container restart wipes paper state | `vinu-live` writes its book (`trade_plan_book.db`) under `VINU_LIVE_DATA_ROOT`, which `docker-compose.yml`'s `live-api` service bind-mounts to `./data/live` — a real host directory, not tmpfs. The tmpfs reference in the original gap doc was about `agent-api`'s `/nonexistent` scratch mount, unrelated to the paper book. | **9/10** — the original claim was actually already wrong even at the time it was documented, or was fixed very early; either way, restart does not lose the book. |
| 18 | ShadowEvaluator never scheduled | `entrypoint.sh` runs `vinu-live shadow-worker &` as a real background daemon on container start, alongside the other three real `while True` workers. `shadow_worker_main()` in `cli.py` is a complete loop, not a stub. **This row is a correction of my own earlier verification error** (I checked only `scheduler.py`, the portfolio-rebalance file, and missed `entrypoint.sh` — see the corrected Scenario 18 block below for the full trail), not a system fix discovered fresh. | **9/10** — genuinely scheduled and running. |

### ❌ STILL OPEN — re-confirmed against current code (30 of 36)

Everything not in the table above was re-checked with a targeted grep for its claimed
fix (calendar/event data, conflict resolution, signal TTL, correlation runtime monitor,
liquidity gate, broker fallback, partial-fill residue handling, data-freshness guard,
PBO persistence, YAML outcome tracking, kill-switch entries-only mode [see the Scenario
21 nuance below], risk-budget enforcement, rebalance force-override, forecast-to-size
wiring, sleeve separation, borrow/dividend/tax modeling, model-disagreement resolution,
OOD/emergency-flatten mode, intra-cycle reconciliation, confidence-gradient allocation)
and **none of these turned up an implementation** — the original verdicts for scenarios
1, 2, 3, 5, 6, 8, 9, 10, 11, 12, 13, 14, 15, 16, 19, 20, 21, 22, 23, 24, 25, 26, 29,
30, 31, 32, 33, 34, 35, 36 stand as originally written.

**Net picture: 6 of 36 fixed, 30 of 36 still open.** Of the 30, the ones worth
prioritizing are 21 and 34, the two remaining DANGEROUSLY MIS-HANDLED scenarios (18 is
now resolved, see below) — those are where the system looks protected but isn't, which
is the costliest kind of gap.

> **Superseded by the "fixes applied this session" block below.** As of 2026-09-09,
> #21 is RESOLVED (both halt layers honour entries-only / `reduce_only`) and #34 is
> downgraded to PARTIALLY HANDLED. This paragraph is the pre-fix snapshot; the
> running tally further down is authoritative.

**2026-09-09 update, fixes applied this session:**
- Stage 1: #17 (CVaR/vol-target flags), #21 (global kill switch now exempts
  reduce-only orders — mirrors the fix already present in vinu-live's local breaker),
  and a related bug found while fixing #21 — vinu-live's `client_order_id` (the #27
  idempotency fix) was computed and sent but silently dropped at the HTTP boundary
  (`OrderRequest` had no such field), so it never reached Alpaca. Now wired end-to-end.
- Stage 2: #22 (risk budget now enforced by `OrderGuard`, plus a separate
  `DailyPositionTracker` persistence bug fixed along the way), #19 (PBO now
  persisted end-to-end and enforced at promotion, plus both read-path gaps closed),
  #24 (forecast confidence now scales position size at both real sizing points —
  `position_sizing.py` and `orchestrator.py`'s live TradePlan entry sizing), #20
  (YAML strategies now get a real directional track record instead of permanent
  "not_tracked"), #36 (TradePlan signal TTL — `created_at` was already being stamped
  at generation time, nothing read it until now; Scenario 9 partially closed as a
  side effect), #8-partial (a real portfolio-wide daily order cap now exists,
  disabled by default; turnover-%/transaction-cost-aware sizing, the scenario's other
  two gaps, remain open — Scenario 8 stays marked PARTIALLY HANDLED, not resolved),
  #34-partial (deflated-Sharpe margin now genuinely tilts daily-allocation weight via
  a new `_confidence_gradient_multiplier`; PBO margin and probationary sizing for
  freshly promoted strategies remain open — downgraded from DANGEROUSLY MIS-HANDLED
  to PARTIALLY HANDLED, not fully resolved).

**Stage 2 is now complete** (all 7 originally-listed items addressed, 2 of them —
#8 and #34 — only partially, both correctly still marked open/partial rather than
resolved).

Updated net picture: **12 of 36 resolved, 24 of 36 still open** (Scenarios 8, 9, and
34 remain open/partial: #8 got a real order-count cap but not a turnover/cost-aware
one; #9 got its signal-TTL half closed by the Scenario 36 fix, but the
hesitation-cost/real-time-alerting half is untouched; #34 got deflated-Sharpe margin
propagated into allocation but not PBO margin or probationary sizing).

See `how-to-make-it-live/` in this folder for the full change log
(`CHANGES-2026-09-09.md`).

---

## SCENARIO 1: FOMO ENTRY — Sudden +5% Move, Incomplete Analysis, Fear of Missing Out

| Field | Determination |
|-------|---------------|
| **Real-world scenario** | Stock gaps +5% pre-market. Trader sees momentum, no complete thesis, enters market order fearing further upside. |
| **Trading phase** | Before Entry → Entry |
| **Human failure** | Chasing price, no plan, no stop, emotional urgency overriding discipline |
| **Bot failure** | Signal triggers on momentum but no validation of thesis completeness |
| **Vina handling** | **PARTIALLY HANDLED** |
| **Existing component(s)** | `OrderGuard` (mandate checks), `TradeTool.submit_order`, `capital_allocator_hook` |
| **Evidence** | `order_guard.py:67-178` — checks: kill switch, blocked tickers, allowed tickers, short restriction, max order value ($50k), daily order limit (10), position pct (25%), capital utilization, active artifact requirement, market hours, portfolio concentration, daily volume |
| **Status details** | **What Vina catches:**<br>• Order rejected if no ACTIVE artifact for symbol (`require_active_artifact: true` default)<br>• Order rejected if exceeds mandate limits (size, daily count, concentration)<br>• Order rejected if market closed (`require_market_open: true`)<br>• Order rejected if kill switch engaged<br>• Human confirmation required (`require_confirmation: true`)<br><br>**What Vina misses:**<br>• **No FOMO detection** — no analysis of "urgency" in order pattern (rapid repeated submissions, market orders vs limit, sizing pressure)<br>• **No thesis completeness check** — `active_artifact` only checks promotion gate passed, not whether *this specific entry* aligns with the artifact's trade plan<br>• **No "chasing" logic** — no check if price moved >X% since signal generation<br>• **No emotional state inference** — the LLM agent *could* reason about this if prompted, but no automated guard |
| **Limitation** | Vina prevents *structurally invalid* orders (no artifact, oversized, halted). It does **not** prevent *behaviorally poor* entries that pass all structural checks. |
| **Real-world consequence** | Trader with valid ACTIVE artifact enters chase trade at +5% extended; all guards pass; position enters at worse price; subsequent reversal causes loss that valid thesis would have avoided |
| **Severity** | **HIGH** — Most common retail/institutional failure mode; Vina's hard guards don't address it |

---

## SCENARIO 2: ENTRY WITH INCOMPLETE INFORMATION — Signal Triggers But Key Data Missing

| Field | Determination |
|-------|---------------|
| **Real-world scenario** | Technical signal fires (e.g., crossover). But: earnings in 2 days (not in data), major news pending, borrow rate spiking for shorts, unusual options activity. Trader enters anyway. |
| **Trading phase** | Before Entry → Entry |
| **Human failure** | Ignoring known unknowns; confirmation bias on signal |
| **Bot failure** | Signal engine doesn't incorporate events calendar, corporate actions, borrow data |
| **Vina handling** | **PARTIALLY HANDLED** (earnings + US-macro blackout added 2026-09-09, Stage 4 `#2`) |
| **Existing component(s)** | `strategy-generate` skill (signal engines), `vinu-stock-price` (data + **new `vinu_stock/events/` calendar + `/stock/events` route**), `initial-analysis` (regime), **`orchestrator._maybe_enter` event-blackout guard (new)** |
| **Evidence** | `strategy-generate/SKILL.md` — signal engines: crossover, threshold, composite, ML. No mention of earnings calendar, news events, borrow rates, corporate actions. `vinu-stock-price` docs show price data only.<br>**Fill applied (2026-09-09):** `vinu_stock/events/{store,finnhub_provider,poller}.py` (local SQLite calendar, daily Finnhub pull via the ingest worker), `service.get_events()` + `GET /stock/events/{symbol}`, `orchestrator.py` `EVENT_BLACKOUT_HOURS` / `entry_blocked_by_event_blackout`. CHANGES §S4-2. Needs `FINNHUB_API_KEY`. |
| **Status details** | **Now handled:**<br>• **Earnings calendar checked before entry** — `/stock/events/{symbol}` within `VINU_LIVE_EVENT_BLACKOUT_HOURS` (default 24h); a hit blocks the entry<br>• **US macro events** (FOMC / CPI / NFP / PCE) via the same calendar, applied to every symbol<br>• Corporate actions (splits/divs) — already handled upstream by Alpaca `adjustment=all` on bars<br><br>**Still open:**<br>• **Borrow availability/rate for shorts** — the not-shortable check (#16) exists, but no borrow-*rate* feed (paid source)<br>• Unusual options flow — not covered<br>• FDA / ad-hoc catalysts not on the earnings or macro calendar<br>• **Exits are not blacked out** (by design — an event is a reason to be *out*, not stuck)<br>• Guard fires on any in-window event regardless of `severity` — no "high-impact only" knob yet |
| **Limitation** | The most common event-risk trade — opening the day before scheduled earnings, or into an FOMC/CPI print — is now blocked. Borrow-rate squeezes, options-flow signals, and unscheduled catalysts remain blind spots. Guard is inert until `FINNHUB_API_KEY` is set (fail-open). |
| **Real-world consequence** | "Enter long day before negative earnings → gap down >10%" is now prevented (`entry_blocked_by_event_blackout`). Borrow-squeeze and pre-split sizing risks remain. |
| **Severity** | **CRITICAL** — reduced: the scheduled-earnings / scheduled-macro vector is closed on the entry side; borrow + ad-hoc catalysts keep the rating critical until a borrow feed lands. |

---

## SCENARIO 3: CONFLICTING SIGNALS — Entry Signal Valid, But Contradictory Signal Appears

| Field | Determination |
|-------|---------------|
| **Real-world scenario** | Strategy A (momentum) signals BUY. Strategy B (mean-reversion) signals SELL. Both have ACTIVE artifacts. Trader/agent must decide. |
| **Trading phase** | Before Entry → Entry |
| **Human failure** | Picking the signal that confirms bias; ignoring contradiction |
| **Bot failure** | No conflict resolution between concurrent ACTIVE strategies on same symbol |
| **Vina handling** | **⚠️ PARTIALLY HANDLED — entry-time conflict block added 2026-09-09 (Stage 3, how-to-make-it-live/CHANGES-2026-09-09.md §S3-3-5)** |
| **Existing component(s)** | `capital_allocator`, `daily-allocation`, `OrderGuard`, `vinu-live` `orchestrator._maybe_enter` / `_opposing_active_signal` |
| **Fix applied** | Before opening a symbol, `_maybe_enter` calls `_opposing_active_signal(plan, symbol, direction, all_plans)` against every other ACTIVE `trade_plan` fetched that cycle; if any has the opposite `direction` it returns `entry_blocked_by_signal_conflict` and places no order. Default policy `block`; `VINU_LIVE_SIGNAL_CONFLICT_POLICY=ignore` restores first-plan-wins. Blocks rather than nets — a deliberate choice (netting trades size nobody sized). |
| **Still open** | Only fires **at entry**, and only between `trade_plan` artifacts (not YAML/quant strategies). No precedence/arbitration rule (it refuses both, doesn't pick a winner), no net-signal sizing, and the allocator can still later fund a counter-strategy — that half is Scenario 5's "open" note. |
| **Limitation** | A fresh entry into a contested symbol is now blocked; two strategies that were funded at different times, or a conflict that emerges after entry, are Scenario 5's territory. |
| **Real-world consequence (now)** | Strategy A long + Strategy B short on the same ticker: whichever tries to open second is rejected with `entry_blocked_by_signal_conflict`, visible in the action log, instead of silently creating the offsetting pair. |
| **Severity** | **HIGH** → **partially mitigated**: simultaneous opposing entries are blocked; cross-strategy arbitration and post-entry conflict handling remain. |

---

## SCENARIO 4: POST-ENTRY — Volatility Increases, Original Setup Weakens

| Field | Determination |
|-------|---------------|
| **Real-world scenario** | Entered long on breakout. Next hour: ATR doubles, volume dries up, price chops around entry. Original thesis (momentum continuation) weakening. |
| **Trading phase** | Management (T+1min → T+1hr) |
| **Human failure** | Hope-based holding; moving stop to breakeven too early; not recognizing regime change |
| **Bot failure** | Static invalidation thresholds; no vol-scaling; no real-time thesis monitoring |
| **Vina handling** | **✅ RESOLVED — verified 2026-09-09** (originally PARTIALLY HANDLED) |
| **Verified** | `orchestrator.py` now runs an unconditional 2×ATR trailing stop (`trailing_stop_for()`, ratchets in favor of the position, never loosens) regardless of whether the plan defines a trailing contingency, PLUS a `max_hold_days` time-stop that force-exits via `_apply_invalidation()` when a position ages past the limit. Both comment-tagged "(15 step2)". Rating: **9/10** — the two named gaps (no default trailing, no time-stop) are genuinely closed. |
| **Existing component(s)** | `vinu-live` Monitor (`orchestrator.py`), `TradePlan` invalidation conditions, `OrderGuard` concentration |
| **Evidence** | `monitor-shock-exit.md` gaps:<br>• Gap #3: No trailing default when plan missing it (`update_stop_loss` only runs if plan has trailing contingency)<br>• Gap #4: Static thresholds, no vol scaling (invalidation -8% fixed; high vol hits noise)<br>• Gap #2: No time-stop (loser sits forever if no invalidation hits)<br>• Good: Cycle every 90s, shock off-cycle trigger, breaker before every order |
| **Status details** | **What Vina catches:**<br>• Monitor cycle (90s) re-evaluates invalidation conditions from `TradePlan`<br>• Shock clustering triggers immediate check (debounce 60s)<br>• Breaker checks daily loss, VaR, exposure before any order<br>• `p_failure` in TradePlan gives probabilistic failure estimate<br><br>**What Vina misses:**<br>• **No vol-scaled invalidation** — -8% threshold same in low/high vol (gap #4)<br>• **No default trailing stop** — only if plan explicitly defines it (gap #3)<br>• **No time-stop** — position can chop indefinitely (gap #2)<br>• **No "thesis weakening" detection** — only binary invalidation hit/miss<br>• **No regime-change re-evaluation** — regime checked daily in allocation, not intra-trade |
| **Limitation** | Monitor is **mechanical invalidation checker**, not adaptive trade manager. It executes the TradePlan as written; if the plan lacks trailing/vol-scaling/time-stop, Vina provides none. |
| **Real-world consequence** | Position chops for days/weeks, tying up capital, missing other opportunities; or volatility spike hits static stop that would be noise in normal vol; or no exit at all until maxDD breach |
| **Severity** | **HIGH** — Trade management is where most edge is lost; Vina's monitor is rigid |

---

## SCENARIO 5: POST-ENTRY — Another Signal Contradicts Original Entry

| Field | Determination |
|-------|---------------|
| **Real-world scenario** | Long position from Strategy A (trend). Strategy B (counter-trend) now signals SHORT on same symbol. Position is open. |
| **Trading phase** | Management |
| **Human failure** | Ignoring new signal; doubling down on original thesis; cognitive dissonance |
| **Bot failure** | No mechanism to re-evaluate open positions against new conflicting signals |
| **Vina handling** | **NOT HANDLED** (entry-time conflicts are now blocked — see Scenario 3 — but this scenario is specifically about a conflict *after* the position is open) |
| **Existing component(s)** | Monitor (checks invalidation), daily-allocation (weights), capital_allocator (funding) |
| **Evidence** | `monitor-shock-exit.md` — Monitor only checks *frozen invalidation conditions* from TradePlan. It does **not** re-run signal generation or check other strategies' signals. `daily-allocation` recomputes weights daily but doesn't trigger position changes. The 2026-09-09 `_opposing_active_signal` fix runs only in `_maybe_enter` (before a position exists), not in `_evaluate_open_position`. |
| **Status details** | **No mechanism for:**<br>• "Signal X fired for open position Y — should we reduce/close?"<br>• Cross-strategy signal monitoring for open positions<br>• Dynamic position adjustment based on new signals (only rebalance_request from capital_allocator — now forceable via `critical`, Scenario 23, but still not signal-driven)<br>• The `rebalance_guard` only checks kill switch, not signal conflicts |
| **Limitation** | Once a position is open, Vina **only** watches its specific invalidation conditions. A new contradictory signal from another strategy on an already-open position is still ignored. |
| **Real-world consequence** | Long trend position held while mean-reversion strategy screams short; position rides reversal that a dynamic system would have reduced. (A *fresh* entry into that conflict is now blocked — Scenario 3.) |
| **Severity** | **HIGH** — the post-entry half is unhandled; only the pre-entry half (Scenario 3) has a guard. |

---

## SCENARIO 6: POST-ENTRY — Market Regime Changes Mid-Trade

| Field | Determination |
|-------|---------------|
| **Real-world scenario** | Entered in bull regime (trending). Mid-trade: VIX spikes, correlation breaks down, regime shifts to high_vol/bear. Original thesis (trend follow) now dangerous. |
| **Trading phase** | Management (T+1hr → T+1day) |
| **Human failure** | Regime blindness; applying bull-market rules in bear market |
| **Bot failure** | Regime used for allocation weighting, not for intra-trade risk adjustment |
| **Vina handling** | **PARTIALLY HANDLED** |
| **Existing component(s)** | `daily-allocation` (`regime.py`), `vinu-portfolio` shock correlation, `Monitor` |
| **Evidence** | `daily-allocation/SKILL.md:37-57` — `classify_current_regime()` reimplements `regime_analysis` angle; fail-open (neutral 1.0). `shock_correlation.py` — DCC-GARCH crisis correlation. `monitor-shock-exit.md` — shock clustering triggers off-cycle check. |
| **Status details** | **What Vina catches:**<br>• Daily allocation recomputes regime → adjusts *future* weights (regime_multiplier)<br>• Shock correlation (DCC-GARCH) detects correlation regime shifts<br>• Shock clustering triggers immediate monitor check<br><br>**What Vina misses:**<br>• **No intra-trade regime adjustment** — regime affects *allocation weights*, not *open position management*<br>• **No "regime invalidation"** — TradePlan invalidation conditions don't include regime change<br>• **Fail-open regime** — if regime fetch fails, multiplier=1.0 (full size), not reduced<br>• **Vocabulary mismatch** — strategies use `trending`/`ranging`/`mean_reverting` tags; regime uses `bull`/`bear`/`high_vol`/`sideways` (documented gap) |
| **Limitation** | Regime change reduces *future allocation* to strategy, but **does not** trigger exit/reduction of existing positions from that strategy. |
| **Real-world consequence** | Trend strategy positions held through regime flip to high_vol/bear; daily allocation reduces new capital to strategy but existing positions ride the drawdown; shock correlation detects it but no action triggered |
| **Severity** | **HIGH** — Regime change is a primary thesis invalidator; Vina detects but doesn't act on it for open positions |

---

## SCENARIO 7: REVENGE TRADING — Two Losses on Same Symbol, Immediate Re-Entry

| Field | Determination |
|-------|---------------|
| **Real-world scenario** | Trader loses on AAPL long. Immediately re-enters AAPL long (same or different strategy). Loses again. Third entry attempted. |
| **Trading phase** | Entry (repeat) |
| **Human failure** | Revenge trading; emotional need to "make it back" on same symbol |
| **Bot failure** | No per-symbol loss memory; no cooldown after losses |
| **Vina handling** | **✅ RESOLVED — verified 2026-09-09** (originally NOT HANDLED) |
| **Verified** | `orchestrator.py:52-104` — `COOLDOWN_LOSSES=2` (`VINU_LIVE_COOLDOWN_LOSSES`), `COOLDOWN_HOURS=24` (`VINU_LIVE_COOLDOWN_HOURS`): 2 consecutive closed losses on a symbol locks new entries for 24h; exits are explicitly exempted (checked separately from the entry path). This is the exact Freqtrade-pattern fix the original gap doc called for. Rating: **9/10**. |
| **Existing component(s)** | `OrderGuard` (daily limits), `Monitor` (debounce 60s), `kill_switch` |
| **Evidence** | `monitor-shock-exit.md` extra #5: "After 2 losses on AAPL, lock AAPL 24h. We have debounce 60s only, no loss lock. Revenge trading possible."<br>`order_guard.py:115-120` — daily order limit (10) but **no per-symbol loss count or cooldown**.<br>`orchestrator.py` — debounce 60s per symbol for shock checks only. |
| **Status details** | **What exists:**<br>• Daily order limit (10 per symbol)<br>• 60s debounce on shock checks<br>• Portfolio drawdown halt at -20%<br><br>**What's missing (explicitly documented):**<br>• **No loss counting per symbol**<br>• **No cooldown after N losses** (Freqtrade pattern: `cooldown_after_loss` + `max_drawdown_pair_lock`)<br>• **No 24h symbol lock after 2 closed losses**<br>• Knobs defined but not built: `VINU_LIVE_COOLDOWN_AFTER_LOSS=2`, `VINU_LIVE_PAIR_LOCK_HOURS=24` |
| **Limitation** | Trader can lose 10 times on same symbol in one day (daily order limit only), with zero friction. |
| **Real-world consequence** | Classic revenge trading spiral: loss → immediate re-entry → loss → larger re-entry → catastrophic loss on single symbol |
| **Severity** | **CRITICAL** — Explicitly documented as gap #5 in monitor; no mitigation exists |

---

## SCENARIO 8: OVERTRADING — High Frequency of Orders Across Symbols

| Field | Determination |
|-------|---------------|
| **Real-world scenario** | Trader/agent submits 50+ orders in a day across many symbols. Many small positions, high turnover, commission drag. |
| **Trading phase** | Entry (repeated) |
| **Human failure** | Overtrading; action bias; commission drag ignored |
| **Bot failure** | No portfolio-level turnover cap; no transaction cost awareness in sizing |
| **Vina handling** | **⚠️ PARTIALLY HANDLED — one of four gaps closed 2026-09-09 (Stage 2, how-to-make-it-live/CHANGES-2026-09-09.md)** |
| **Existing component(s)** | `OrderGuard` (daily limits, throttle, now portfolio-wide cap), `daily-allocation` (weights), `capital_allocator` (budget) |
| **Evidence** | `order_guard.py:89-95` — throttle: 10 orders/sec per instance (in-process burst limit).<br>`order_guard.py:115-120` — `max_daily_orders: 10` per symbol.<br>`order_guard.py:169-176` — `max_daily_trade_volume: $200k`.<br>**New**: `mandate.max_daily_orders_portfolio` (default 0 = disabled) + `DailyLimitStore.count_today_total()` — a real portfolio-wide daily order cap, checked in `OrderGuard.check()`, `reduce_only` orders exempt.<br>`daily-allocation/SKILL.md` — weights renormalize to 1.0; no turnover penalty (unchanged).<br>`money-gate.md` gap #4 — "No gross cap tick. Paper tests single, live holds batch." (unchanged) |
| **Status details** | **What's now handled (new):**<br>• Portfolio-level daily order cap — configurable via mandate's `max_daily_orders_portfolio`, defaults to 0/disabled since the right ceiling depends entirely on how many symbols a given deployment trades<br><br>**What Vina still catches (unchanged):**<br>• Per-symbol daily order cap (10)<br>• Per-symbol daily volume cap ($200k)<br>• 10 orders/sec burst throttle (per process)<br>• Capital allocator budget ($100k default) limits total deployed<br><br>**What Vina still misses:**<br>• **No turnover cap** — no limit on portfolio turnover %, a distinct metric from raw order count<br>• **No transaction cost integration in sizing** — costs ignored in Kelly/position sizing (money-gate gap #2)<br>• **No "commission drag" awareness** — simulation uses 0.1% + 0.05% slippage; live 0.2-0.5%/turn |
| **Limitation** | The specific "10/symbol × 20 symbols = 200/day" gap this scenario opened with is closed (once the operator sets a non-zero cap — it ships disabled). Turnover-as-a-percentage and transaction-cost-aware sizing remain open, larger pieces of work (money-gate gap #2 territory, Stage 4). |
| **Real-world consequence** | High turnover strategy bleeds 30%+ annually to costs (money-gate: 100 turns × 0.3% = 30% drag); portfolio churns without edge — cost drag itself is unaddressed by this fix, only the raw order-count ceiling |
| **Severity** | **HIGH** — Cost drag is silent killer; Vina sim doesn't match live |

---

## SCENARIO 9: HESITATION — Valid Signal, Trader/Agent Freezes, Misses Entry

| Field | Determination |
|-------|---------------|
| **Real-world scenario** | TradePlan generated with valid setup. Price at entry zone. Trader/agent hesitates (fear, uncertainty). Price moves away. Entry missed. |
| **Trading phase** | Before Entry |
| **Human failure** | Analysis paralysis; fear of loss > desire for gain |
| **Bot failure** | No "signal aging" tracking; no auto-execution on valid signal; no hesitation cost measurement |
| **Vina handling** | **⚠️ PARTIALLY HANDLED — upgraded 2026-09-09 (Stage 2, how-to-make-it-live/CHANGES-2026-09-09.md)** |
| **Existing component(s)** | `TradePlan` (forecast, invalidation, `created_at`), `Monitor`/`_maybe_enter` (now checks signal age, see Scenario 36), `shadow-account` skill (post-hoc) |
| **Evidence** | `shadow-account/SKILL.md:28` — "Behavioral scoring: FOMO trades, revenge trades, **hesitation cost**" — still post-trade journal analysis only, unchanged.<br>`orchestrator.py`'s `_maybe_enter()` now rejects a plan whose signal has aged past `VINU_LIVE_SIGNAL_MAX_AGE_HOURS` (default 72h) — see Scenario 36 for the fix detail; the same fix closes half of this scenario. |
| **Status details** | **What's now handled:** signal time-to-live / expiration — a stale, never-triggered plan is now rejected instead of remaining actionable indefinitely.<br><br>**Still NOT handled:** auto-execution on a valid signal (human confirmation is still required by default — a deliberate design choice, not a bug); measuring hesitation cost in real time; alerting "valid setup aging, decision needed" before it actually expires. The signal-TTL fix stops a *stale* signal from being acted on late; it does nothing to help a human/agent notice and act on a *fresh* one faster. |
| **Limitation** | Vina still has **no ownership of execution timing** for the "should I act now" decision — only for the "has this gone stale" cutoff. Missed entries within the TTL window remain invisible to the system. |
| **Real-world consequence** | Reduced but not eliminated: a setup missed within the TTL window is still silently missed; the system now at least refuses to act on ones aged well past that window |
| **Severity** | **MEDIUM** — Hard to automate without removing human agency; but measurable |

---

## SCENARIO 10: STOP-LOSS BEHAVIOR — Stop Hit, But Was It Noise or Thesis Break?

| Field | Determination |
|-------|---------------|
| **Real-world scenario** | Long position. Stop-loss at -5% hit. Price immediately reverses and goes +10%. Was stop correct (risk control) or noise (premature exit)? |
| **Trading phase** | Exit |
| **Human failure** | Moving stop after entry; removing stop; "mental stop" not honored |
| **Bot failure** | No stop-loss quality analysis; no distinction between noise stop and thesis break |
| **Vina handling** | **PARTIALLY HANDLED** |
| **Existing component(s)** | `TradePlan` (invalidation conditions), `Monitor` (checks invalidation), `OrderGuard` (bracket orders via `take_profit_price`, `stop_loss_price`), `shadow-account` (post-hoc) |
| **Evidence** | `trade_tool.py:60-71` — supports `take_profit_price` and `stop_loss_price` for bracket orders at entry.<br>`monitor-shock-exit.md` gap #3 — trailing stop only if plan has it; gap #4 — static thresholds.<br>`orchestrator.py:511` — `update_stop_loss` exists but only for trailing contingency actions. |
| **Status details** | **What Vina catches:**<br>• Bracket orders at entry (real stop order resting at broker)<br>• Monitor checks invalidation conditions mechanically<br>• Shadow-account analyzes stop quality *post-hoc*<br><br>**What Vina misses:**<br>• **No real-time stop quality classification** — was it noise (ATR-based) vs thesis break (structural)?<br>• **No adaptive stop** — static or trailing only per plan; no vol-scaling (gap #4)<br>• **No "stop moved" audit** — if human moves stop, no guard prevents it (bracket orders help but not mandatory)<br>• **No distinction in logging** — stop hit = exit; no metadata on *why* |
| **Limitation** | Stops are executed mechanically. Quality analysis only exists in post-trade shadow account. No learning loop feeds back to strategy. |
| **Real-world consequence** | Repeated noise stops erode edge; no feedback to widen stops in high vol or tighten in low vol; trader learns nothing from stop hits |
| **Severity** | **MEDIUM** — Bracket orders help; but no adaptive logic or learning |

---

## SCENARIO 11: THESIS INVALIDATION — Price Moves Against Position, But Original Thesis Still Valid

| Field | Determination |
|-------|---------------|
| **Real-world scenario** | Long on earnings momentum thesis. Price drops -7% on market-wide selloff (not company-specific). Thesis intact (earnings still coming, momentum still valid post-earnings). Trader must decide: hold or exit. |
| **Trading phase** | Management |
| **Human failure** | Exiting valid thesis on market noise; or holding invalid thesis on hope |
| **Bot failure** | Binary invalidation; no "thesis vs market noise" discrimination |
| **Vina handling** | **PARTIALLY HANDLED** |
| **Existing component(s)** | `TradePlan` (invalidation_conditions, `p_failure`), `Monitor`, `daily-allocation` (regime) |
| **Evidence** | `TradePlan` has `invalidation_conditions` (metric, operator, threshold) and `p_failure` (probability of failure). `Monitor` evaluates these mechanically. `daily-allocation` has regime multiplier but doesn't affect open positions. |
| **Status details** | **What Vina catches:**<br>• Explicit invalidation conditions in TradePlan (e.g., "price < support", "RSI > 80")<br>• `p_failure` gives probabilistic failure estimate<br>• Monitor checks every 90s + shock triggers<br><br>**What Vina misses:**<br>• **No "thesis vs market" decomposition** — invalidation is binary (condition met/not met)<br>• **No regime-relative invalidation** — -7% drop in high_vol regime may be noise; in low_vol it's signal<br>• **No "thesis still valid" flag** — once invalidation hits, position exits; no "hold despite invalidation if thesis intact" logic<br>• **No correlation-adjusted stops** — market-wide move vs idiosyncratic not distinguished |
| **Limitation** | Invalidation is **mechanical and absolute**. No context-aware "thesis survival" assessment. |
| **Real-world consequence** | Valid thesis positions stopped out on market noise; or invalid thesis positions held because invalidation condition not precisely defined |
| **Severity** | **HIGH** — Core trading skill: distinguishing noise from signal breakdown; Vina has no mechanism for this |

---

## SCENARIO 12: CORRELATED POSITIONS — Multiple Positions Move Together Unexpectedly

| Field | Determination |
|-------|---------------|
| **Real-world scenario** | Long AAPL, MSFT, NVDA (all tech). Market correlation spikes to 0.9. All three hit stops simultaneously. Portfolio loses 3x single-position risk. |
| **Trading phase** | Management → Exit (cascading) |
| **Human failure** | False diversification; thinking 3 positions = 3x risk reduction; correlation blindness |
| **Bot failure** | Correlation checked at promotion/order time only; no runtime correlation monitoring for open positions |
| **Vina handling** | **⚠️ PARTIALLY HANDLED — runtime monitor added 2026-09-09 (Stage 3, how-to-make-it-live/CHANGES-2026-09-09.md §S3-12)** |
| **Existing component(s)** | `OrderGuard` (portfolio concentration check at order time), `vinu-portfolio` (shock correlation DCC-GARCH), `daily-allocation`, `vinu-live` `orchestrator._check_runtime_correlation` |
| **Fix applied** | `vinu-live` `orchestrator._check_runtime_correlation(prices)` runs every cycle: reuses `_compute_covariance` (DCC/shrinkage) → `correlation_from_covariance`, computes each open pair's co-movement *in the direction the book is exposed* (`corr · sign(expo_a) · sign(expo_b)` — a correlated long+short is a hedge, not flagged), and `reduce_only`-trims the **larger** position of any pair at/above `VINU_LIVE_RUNTIME_CORR_THRESHOLD` (0.85) by `VINU_LIVE_RUNTIME_CORR_REDUCE_PCT` (25%), once per `VINU_LIVE_RUNTIME_CORR_COOLDOWN_SEC` (1h) per symbol. Default ON. |
| **Still open** | No **portfolio-level** stop (a "total DD from correlated move > X% → flatten" action); the trim is pairwise-greedy (larger of each flagged pair), not an optimiser that picks the minimum set of cuts; 1D/1H **sleeves** still not built (Scenario 25); `vinu-portfolio`'s `crisis_correlation`/`shock_delta` at the daily-allocation layer still only steer *new* capital, not open positions (this fix is the `vinu-live` side only). |
| **Limitation** | Correlated open positions are now actively trimmed pair-by-pair; there is still no single portfolio-wide correlated-drawdown circuit beyond the existing −20% breaker. |
| **Real-world consequence (now)** | Long AAPL+MSFT+NVDA with correlation spiking to 0.9: each cycle the largest of each 0.85+ pair is cut 25% (hourly per name), bleeding down the concentrated exposure instead of riding it fully into the correlated crash. |
| **Severity** | **CRITICAL** → **partially mitigated**: open-position correlation is now acted on, not just measured; a portfolio-level correlated-DD stop and sleeve isolation remain. |

---

## SCENARIO 13: LIQUIDITY DISAPPEARS — Spread Widens, Partial Fills, Slippage Spikes

| Field | Determination |
|-------|---------------|
| **Real-world scenario** | News hits. Spread widens 10x. Market orders fill at terrible prices. Limit orders don't fill. Position can't be exited cleanly. |
| **Trading phase** | Entry / Exit |
| **Human failure** | Market orders in illiquid conditions; not using limits; underestimating slippage |
| **Bot failure** | No liquidity awareness; fixed slippage model; no partial fill handling |
| **Vina handling** | **PARTIALLY HANDLED** (entry-side spread gate added 2026-09-09, Stage 4 `#13`) |
| **Existing component(s)** | `trade_tool.py` (order types), `OrderGuard` (price bands?), `vinu-simulator` (cost model), **`vinu-stock-price` `/stock/quote` + `orchestrator._maybe_enter` spread gate (new)** |
| **Evidence** | `trade_tool.py:42-46` — supports `market`, `limit`, `stop`, `stop_limit`.<br>`money-gate.md` gap #2 — "Sim 0.001 + slippage 0.0005 fixed. Live spread + queue + latency + partial + borrow + fees 0.2 to 0.5 percent per turn."<br>`costs.py:73`, `execution.py:33` — fixed cost model.<br>`16-broker-fills.md` gaps — partial fills, queue position, latency not modeled.<br>**Fill applied:** `vinu_stock/providers/quote.py`, `service.py` (`get_quote`, 5s TTL), `routes_read.py` (`GET /stock/quote/{symbol}`), `orchestrator.py` (`MAX_SPREAD_BPS` / `_spread_bps_from_quote` / `entry_blocked_by_wide_spread`). CHANGES §S4-13. |
| **Status details** | **Now handled:**<br>• **Real-time spread monitoring at order time** — live Alpaca NBBO, 5s-cached<br>• **Liquidity gate — block ENTRY when spread_bps > `VINU_LIVE_MAX_SPREAD_BPS` (default 25 = 0.25%)**; fail-open if no quote<br>• Partial-fill management — already added Stage 3 `#15` (`_confirm_fill`, books actual filled qty)<br><br>**Still open:**<br>• **Exits are NOT spread-gated** (by design — a trapped position must still be exitable) — so the news-spike exit-slippage case is unmitigated<br>• No L2 depth / book-impact check (`VINU_LIVE_MAX_BOOK_PCT` deferred)<br>• No dynamic order-type selection (market vs limit vs algo)<br>• Slippage cost model still fixed (0.1% + 0.05%) in sim<br>• No queue-position awareness |
| **Limitation** | Entry side is now protected against opening into a blown-out spread. Exit side, the adaptive cost model, and order-type selection are unchanged. |
| **Real-world consequence** | Entries into a news-spike wide market are now blocked (`entry_blocked_by_wide_spread`). Exit slippage during a liquidity event is still taken. |
| **Severity** | **CRITICAL** — Money-gate gap #2: "Gross 1.0 becomes net 0.2" — 80% edge destroyed by costs. Entry-side spread gate trims the worst of it; residual is exit slippage + fixed cost model. |

---

## SCENARIO 14: SYSTEM OUTAGE — Broker API Down, Data Feed Stale, Cannot Exit

| Field | Determination |
|-------|---------------|
| **Real-world scenario** | Alpaca API down. Polygon data lagging 30min. Position open. Market moving against position. Cannot submit exit order. |
| **Trading phase** | Management / Exit |
| **Human failure** | Panic; no backup plan; manual intervention impossible |
| **Bot failure** | No fallback broker; no stale data detection; no "outage mode" |
| **Vina handling** | **PARTIALLY HANDLED** |
| **Existing component(s)** | `kill_switch` (halt), `OrderGuard` (fail-open on broker errors), `Monitor` (reconciliation), `health banner` (UI), **`orchestrator._check_broker_health()` broker-outage pause (new)** |
| **Evidence** | `money-gate.md` gap #7 — "Alpaca down, Polygon lag, LLM 400 fail, portfolio unreachable funding skipped fail-closed. Stuck flat cannot exit on outage."<br>`monitor-shock-exit.md` — `VINU_LIVE_TURBULENCE_PAUSE_ENTRIES` knob (not built).<br>`kill_switch.py` — filesystem-based, works across processes.<br>`order_guard.py:132-133, 151-152` — broker errors → `logger.warning` → **fail-open (allows order)**.<br>**Fill applied (Half A, 2026-09-09):** `orchestrator.py` — `_check_broker_health()` runs once per cycle before the plan loop; `BROKER_STALE_SEC` (`VINU_LIVE_BROKER_STALE_SEC`, default 180, 0 disables); `self._broker_degraded` → `_maybe_enter` returns `entry_blocked_by_broker_outage`. CHANGES §S4-14A. |
| **Status details** | **What Vina catches:**<br>• Kill switch works via filesystem (independent of broker API)<br>• OrderGuard fails *open* on broker errors (allows order rather than blocking)<br>• Monitor reconciles book vs broker every cycle<br>• **NEW: broker-outage pause** — a per-cycle `/agent/broker/account` probe; if it stays unreachable past `BROKER_STALE_SEC` (or has never answered since worker start), new **entries** pause automatically and resume on the next healthy probe. Exits/reduces are **never** gated.<br><br>**Still open:**<br>• **No fallback broker** — Half B (`VINU_AGENT_BROKER_ORDER=alpaca,<2nd>` + a 2nd `Broker` impl) is the next `#14` item, not yet built → **still no exit path while the sole broker is down**<br>• **No stale-*data*-feed pause distinct from broker** — data-freshness guard (#16) pauses entries on a stale price feed but there is no "allow exits, pause entries" split tied to feed lag specifically<br>• Health banner still UI-only for the human |
| **Limitation** | Entry side now auto-pauses on a detected broker outage and auto-resumes. The **exit path during an outage is unchanged** — with a single broker down, an open position still cannot be exited until Half B (second venue) lands. |
| **Real-world consequence** | New entries stop within one cycle of the broker going dark (no orders fired blindly into a dead API). An already-open position still can't be exited during a full outage of the only broker. |
| **Severity** | **CRITICAL** — reduced on the entry side; the single-point-of-failure exit risk remains until `#14` Half B. Documented as gap #7 in money-gate. |

---

## SCENARIO 15: PARTIAL FILL — Order Partially Filled, Rest Unfilled, Market Moves

| Field | Determination |
|-------|---------------|
| **Real-world scenario** | Limit order for 1000 shares. 200 filled. Price moves away. 800 unfilled. Position now 200 shares (not planned size). |
| **Trading phase** | Entry / Management |
| **Human failure** | Not managing partial fill; leaving unfilled residue; averaging at worse prices |
| **Bot failure** | No partial fill handling logic; no residue management |
| **Vina handling** | **⚠️ PARTIALLY HANDLED — fill tracking added 2026-09-09 (Stage 3, how-to-make-it-live/CHANGES-2026-09-09.md §S3-15)** |
| **Existing component(s)** | `trade_tool.py` (submits order), `HistoricalFillBroker` (replay), Alpaca broker (live), `vinu-live` `orchestrator._maybe_enter` / `_reconcile_book_with_broker` |
| **Fix applied** | `_maybe_enter()` no longer books the intended qty on `submitted`; it snapshots the broker's position, polls `/agent/broker/positions` (`VINU_LIVE_FILL_CONFIRM_ATTEMPTS`×`_DELAY_SEC`) and books the **actual filled** qty, flagging `partial_fill`/`intended_qty` in the action on a shortfall. `_reconcile_book_with_broker()` — which already ran every cycle but only logged — now **corrects** the book toward broker truth (`VINU_LIVE_RECONCILE_AUTOCORRECT`): reduce/close on book>broker, add on book<broker (same side), and alert-without-change on side conflicts, phantom broker positions, or an implausible (`>MAX_RATIO`) gap. Both fail open when the broker snapshot is empty/untrusted. |
| **Still open** | **Residue cancellation** — no `GET`/`DELETE /agent/broker/order/{id}` route exists, so a still-open working order can't be explicitly killed (market/day orders resolve intra-session, so exposure is tracked even though the residual order isn't). Exits/reduces get only the one-cycle-lagged reconciliation backstop, not an in-cycle `_confirm_fill` like entries. No re-submission of the unfilled remainder. |
| **Limitation** | The account's *real exposure* is now tracked and the book self-heals within a cycle; the *unfilled remainder* still isn't actively managed. |
| **Real-world consequence (now)** | A 200-of-1000 fill books 200, and risk/exit/P&L run off 200; the 800 residue still sits until the exchange resolves it, and isn't re-submitted. |
| **Severity** | **HIGH** → **partially mitigated**: "risk limits on intended not actual size" is fixed for the entry path + reconciliation; residue management and exit-path in-cycle confirmation remain. |

---

## SCENARIO 16: DATA STALENESS — Decisions Made on 30-Minute Old Data

| Field | Determination |
|-------|---------------|
| **Real-world scenario** | Data pipeline lagging. Agent/Monitor makes decisions on prices 30min old. Market moved significantly. |
| **Trading phase** | All phases |
| **Human failure** | Not checking data freshness; trusting stale signals |
| **Bot failure** | No data freshness SLA; no "stale data = no trade" guard |
| **Vina handling** | **⚠️ PARTIALLY HANDLED — entry guard added 2026-09-09 (Stage 3, how-to-make-it-live/CHANGES-2026-09-09.md §S3-16)** |
| **Existing component(s)** | `vinu-stock-price` (ingestion), `initial-analysis` (freshness), `Monitor` (live metrics), `18-data-pipeline.md` |
| **Fix applied** | `vinu-live` `orchestrator._fetch_prices()` now records the newest bar's `bar_ts` per symbol; `_maybe_enter()` returns `entry_blocked_by_stale_data` (and never calls the broker) when that timestamp is older than `VINU_LIVE_PRICE_MAX_AGE_HOURS` (default 96h — tuned for daily bars over a long weekend; must be tightened for intraday intervals). `_evaluate_open_position()` detects the same staleness but only logs it — exits/reduces are never gated on freshness, same entries-only shape as HALT/turbulence/cooldown. Fail-open when no timestamp is available. |
| **Still open** | The guard lives only in `vinu-live`'s trade-plan loop. `OrderGuard` (the shared order gate for the LLM `submit_order` tool) has no freshness check; a market-calendar-aware "is this the latest expected session" check (tighter than a wall-clock hour threshold) still needs the calendar data source Scenario 2 is about; the LLM agent path and `initial-analysis` are unguarded. |
| **Limitation** | Automated trade-plan entries are now gated; a manual/agent order or an analysis run still isn't. |
| **Real-world consequence (now)** | An automated entry against a feed that stalled >96h ago is blocked; open positions still evaluate (so a real invalidation on a stale-but-moving mark still fires an exit). |
| **Severity** | **CRITICAL** → **partially mitigated**: the automated entry path no longer trades blind on a dead feed; the shared `OrderGuard` and agent paths still can. |

---

## SCENARIO 17: POSITION SIZING — Kelly Sizing on Noisy Edge, No CVaR Gate

| Field | Determination |
|-------|---------------|
| **Real-world scenario** | Strategy shows Sharpe 1.2 in backtest (30 trades). True edge unknown. Kelly fraction suggests 20% position. Vol targeting caps at 15% portfolio vol. |
| **Trading phase** | Before Entry (sizing) |
| **Human failure** | Overbetting on lucky backtest; ignoring parameter uncertainty |
| **Bot failure** | Kelly on point estimate; no CVaR; no dynamic vol targeting |
| **Vina handling** | **⚠️ BUILT BUT DISABLED — verified 2026-09-09** (originally PARTIALLY HANDLED) |
| **Verified** | `vinu-agent/vinu_agent/agent/position_sizing.py` — `cvar_exceeds()` blocks sizing to 0 when CVaR95 exceeds threshold; `vol_target_scale()` scales size by `target_vol/current_vol`. Wired into the real order path through `risk_gatekeeper_hook.py` (not just a standalone tool). **But `VINU_RISK_CVAR_ENABLED` and `VINU_RISK_VOL_TARGET_ENABLED` both default to `false`.** Rating: **6/10** — production-ready code sitting behind an off switch. Flipping two env vars closes this scenario for real. |
| **Existing component(s)** | `position_sizing.py` (fractional_kelly 0.25), `daily-allocation` (vol-target 15% cap 1x), `risk-allocation-full.md` |
| **Evidence** | `position_sizing.py:15` — `fractional_kelly 0.25` (quarter-Kelly).<br>`risk-allocation-full.md` Now #1 — "Tail risk gate VaR/CVaR: Web has mean-CVaR, CDaR, Ulcer. We check maxDD -0.25 only, no CVaR 95%."<br>Now #2 — "Volatility targeting dynamic: Need dynamic: `position = target_vol / current_vol`. High vol halves size auto."<br>Knobs defined: `VINU_RISK_CVAR_ENABLED`, `VINU_RISK_VOL_TARGET_ENABLED` — **not built**. |
| **Status details** | **What Vina catches:**<br>• Quarter-Kelly cap (0.25) — conservative vs full Kelly<br>• Fixed-fractional fallback (1-2% rule)<br>• ATR-based sizing fallback<br>• Portfolio vol-target 15% cap (static)<br>• Concentration headroom cap<br><br>**What Vina misses (documented gaps):**<br>• **No CVaR 95% gate** — only maxDD -25% checked<br>• **No dynamic vol targeting** — static 15% cap; no `position = target_vol / current_vol`<br>• **No DD halve** — position not reduced as drawdown increases<br>• **No parameter uncertainty in sizing** — Kelly on point estimate |
| **Limitation** | Sizing is conservative (quarter-Kelly) but **static**. No tail risk gate, no dynamic vol adjustment, no drawdown-responsive sizing. |
| **Real-world consequence** | Position sized for backtest vol; live vol doubles → position risk doubles; no CVaR gate to catch tail; drawdown deepens without size reduction |
| **Severity** | **HIGH** — Explicitly documented as Now #1, #2 in risk-allocation; not built |

---

## SCENARIO 18: PROMOTION WITHOUT PAPER TRADING — Artifact Promoted to ACTIVE, Never Paper-Traded

| Field | Determination |
|-------|---------------|
| **Real-world scenario** | Strategy passes promotion gate (deflated Sharpe, holdout, stress test). Promoted to ACTIVE. Immediately gets live capital. Never paper-traded. |
| **Trading phase** | Before Entry (capital allocation) |
| **Human failure** | Trusting backtest; skipping paper validation |
| **Bot failure** | ShadowEvaluator built but never called; no paper-trading enforcement |
| **Vina handling** | **✅ RESOLVED — CORRECTED 2026-09-09.** My earlier "still dead code" verdict was a verification error, not a real finding — I only checked `vinu-live/vinu_live/scheduler.py` (the portfolio-rebalance cycle file) for a `ShadowEvaluator` reference and found none, then wrongly generalized that to "never scheduled." I never checked `vinu-live/entrypoint.sh`, the container's actual multi-process startup script. |
| **Existing component(s)** | `promotion.py` (promotion gate), `ShadowEvaluator` (paper check), `cli.py`'s `shadow_worker_main()`, `entrypoint.sh` |
| **Corrected evidence** | `vinu-live/entrypoint.sh` starts `vinu-live shadow-worker &` as a background daemon alongside `vinu-live-worker`, `trade-plan-worker`, `feedback-worker`, and the foreground `serve` process — same pattern as the other three real workers. `cli.py:117-162`'s `shadow_worker_main()` is a complete `while True: evaluate_all(); sleep(interval)` loop, not a stub — its own docstring says "Phase 4/5's own implementation records flagged as missing ('ShadowEvaluator still has no scheduled caller')... evaluate_all() was already correct and tested, just never invoked on a cadence" — past tense, describing a gap that `entrypoint.sh`'s "Scheduler-wiring follow-up (...phase-9-scheduler-wiring/)" comment confirms was closed. Rating: **9/10** — genuinely scheduled and running; the only residual question is whether every ACTIVE artifact in your deployment was promoted *after* this wiring landed (anything promoted before wouldn't retroactively gain paper history). |
| **Status details** | The original `live-safety/SKILL.md` and `daily-allocation/SKILL.md` quotes describing this as dormant were accurate *at the time those docs were written* — the "Scheduler-wiring follow-up" comment in `entrypoint.sh` shows the fix landed in a later phase (phase-9) than those two docs describe (phase 4/5/7). This is the same pattern as Scenario 28: a doc correctly described a gap that was later closed, and the doc was never updated. |
| **Limitation** | None remaining for the scheduling gap itself. Not re-verified in this pass: whether `evaluate_all()`'s actual pass/fail thresholds are strict enough, and whether its verdict is wired back into the promotion/allocation decision (i.e., does a paper-trading FAIL actually stop capital, or only get logged) — that's a different, narrower question than "is it scheduled," and would need its own check. |
| **Real-world consequence** | None from this specific gap — it's closed. If you want certainty beyond this correction, check your deployment logs for `[shadow-worker] Starting` on container boot. |
| **Severity** | Downgraded from CRITICAL to **N/A (resolved)**. |

---

## SCENARIO 19: PBO NOT PERSISTED — Selection Bias Invisible After Research Run Completes

| Field | Determination |
|-------|---------------|
| **Real-world scenario** | Research run tests 50 parameter combinations. Best one has Sharpe 2.0. PBO = 0.75 (severe overfitting). Run completes. Later, operator checks artifact — no PBO visible. |
| **Trading phase** | Post-research / Pre-promotion |
| **Human failure** | Forgetting PBO warning; promoting overfit strategy |
| **Bot failure** | PBO computed but not stored; cannot be checked at promotion time |
| **Vina handling** | **✅ RESOLVED — fixed 2026-09-09 (Stage 2, how-to-make-it-live/CHANGES-2026-09-09.md)** |
| **Existing component(s)** | `pbo.py` (computation), `gatekeepers/SKILL.md`, `ResearchStorage`, `SqliteStrategyStore`, `promotion.py` |
| **Fix applied** | PBO now flows through the entire chain that was previously broken at every step: (1) `ResearchRunRecord.pbo` and `Artifact.pbo` fields added; (2) `research_runs.pbo` and `artifacts.pbo` REAL columns added via the existing migration mechanisms in both `sqlite_backend.py` and `strategy_store.py`; (3) `ResearchService.run_research()` now sets `record.pbo = result.pbo.get("pbo")` right alongside the existing `holdout_passed`/`stress_test_passed` assignment, and `_create_artifact_from_run()` copies it onto the `Artifact` at promotion-candidate creation time; (4) `promotion.meets_promotion_bar()` gained a PBO check (`promotion_pbo_required=True` default, `promotion_pbo_threshold=0.7` default, matching `sweep_grid.py`'s existing `pbo_severe` convention) — rejects with an explicit reason if PBO is missing (required-but-never-computed) or above threshold, same posture as the existing holdout/stress-test checks; (5) both read-path gaps closed too — `GET /research/runs/{id}` (via `ResearchRunRecord.to_dict()`) and the artifact-list endpoint now both return `pbo`. |
| **Status details** | **What exists now:**<br>• PBO persists from research run through to promotion decision — no longer ephemeral<br>• Promotion gate rejects both "PBO too high" and "PBO required but never computed" (an unset holdout is already treated as a rejection reason; PBO now follows the identical pattern)<br>• Both read endpoints (`GET /research/runs/{id}`, artifact list) surface it<br>• Configurable via `VINU_RESEARCH_PROMOTION_PBO_THRESHOLD` / `VINU_RESEARCH_PROMOTION_PBO_REQUIRED`<br><br>**Not done:** no backfill for pre-existing rows — artifacts/runs created before this fix have `pbo = NULL` in the new column, which the promotion gate (correctly, by design) treats as "required but never computed" and rejects unless `promotion_pbo_required` is explicitly set to `false` or the artifact is re-approved through a fresh run. |
| **Real-world consequence (before the fix)** | Overfit strategy (PBO > 0.7) promoted because PBO not visible at promotion decision; live trading fails |
| **Severity** | Downgraded from HIGH to **N/A (resolved)**. |

---

## SCENARIO 20: YAML STRATEGIES HAVE ZERO OUTCOME TRACKING

| Field | Determination |
|-------|---------------|
| **Real-world scenario** | 4 YAML strategies (built-in) trading live. No calibration entries ever recorded. Daily allocation gives them neutral outcome multiplier (1.0). They get full capital allocation weight regardless of actual performance. |
| **Trading phase** | Ongoing (daily allocation) |
| **Human failure** | Assuming all ACTIVE strategies are equally validated |
| **Bot failure** | Outcome tracking only for `trade_plan` artifacts; YAML strategies invisible to calibration |
| **Vina handling** | **✅ RESOLVED — fixed 2026-09-09 (Stage 2, how-to-make-it-live/CHANGES-2026-09-09.md)** |
| **Existing component(s)** | `daily-allocation/SKILL.md`, `MetaStorage`, `FeedbackLoopWorker`, `PortfolioService._fetch_yaml_track_record` (new) |
| **Fix applied** | YAML strategies have no `artifact_id` and no discrete open/closed positions the way `trade_plan` strategies do, so this doesn't reuse `calibration_entries` — it derives a genuine directional track record from two series `vinu-portfolio` already fetches elsewhere: the strategy's own historical target-weight series (`weights_source`) and the symbol's own price history. For each pair of consecutive dates where the strategy held a non-flat weight the day before, it checks whether that weight's sign (long/short) matched the symbol's realized return sign — a flat/near-zero weight is excluded as "no call made," not scored as wrong. `_fetch_outcome_confidence()` now routes `kind == "yaml"` to this new `_fetch_yaml_track_record()` instead of a hardcoded `"not_tracked"`. |
| **Status details** | **What exists now:**<br>• A YAML strategy with enough trading history gets a real `{"source": "yaml_track_record", "accuracy": <float>, "n_entries": <int>}` — feeds into the exact same `_outcome_confidence_multiplier()` that already tilts allocation for `trade_plan` artifacts, no changes needed there<br>• Still fails open to `"not_tracked"` (never a fabricated number) when weight or price history is unavailable, and `"insufficient_data"` below `min_calibration_entries_for_tilt` — same three-state contract the original code already had, just genuinely reachable now<br><br>**Still not done:** no P&L-dollar tracking, only directional accuracy — matches what `trade_plan` calibration already measures (directional correctness), not a full P&L attribution system. `MetaStorage` (the separate `vinu-strategy` service's registry) itself was not touched — this fix computes the track record on read, in `vinu-portfolio`, rather than persisting it as new columns on that table, which avoids a second service needing new write logic for the same information. |
| **Real-world consequence (before the fix)** | YAML strategy degrades (regime change, edge decay); continues receiving full allocation; no signal to reduce/remove; capital wasted |
| **Severity** | Downgraded from HIGH to **N/A (resolved)**. |
| **Severity** | **HIGH** — Explicitly documented; 4 strategies unmonitored |

---

## SCENARIO 21: KILL SWITCH HALTS EXITS — Position Trapped During Crash

| Field | Determination |
|-------|---------------|
| **Real-world scenario** | Portfolio drawdown hits -20%. `PortfolioDrawdownMonitor` calls `POST /broker/halt`. Global kill switch engages. Position moves -30% further. Trader wants to exit. System blocks exit order. |
| **Trading phase** | Exit (during crisis) |
| **Human failure** | Not anticipating kill switch blocks exits; no manual override ready |
| **Bot failure** | Kill switch doesn't distinguish entries vs exits; HALT_ALL blocks everything |
| **Vina handling** | **✅ RESOLVED — fixed 2026-09-09 (Stage 1, how-to-make-it-live/CHANGES-2026-09-09.md §2)** |
| **Verified (re-check history)** | Original re-check found **two separate halt mechanisms**, only one fixed: (1) `vinu-live`'s local breaker (`orchestrator.py`, `check_limits()`) already did entries-only via `HALT_POLICY=entries_only` / `_halt_allows_exit()`; (2) the **global filesystem kill switch** (`kill_switch.py`, engaged by `PortfolioDrawdownMonitor` at -20% DD via `POST /broker/halt`), checked inside `OrderGuard.check()`, rejected *everything* regardless of `side` — so an exit clearing the local breaker still got rejected here. **This is now fixed** (see Fix applied below); the doc-only Scenario 21 block had lagged the code — corrected during the re-audit. |
| **Fix applied** | `OrderGuard.check()` / `pre_approve()` gained a `reduce_only: bool` flag and `_halt_policy_allows_reduce_only()` (reads the **same** `VINU_LIVE_HALT_POLICY`, default `entries_only`, so the two halt layers share one policy knob). When the kill switch is engaged AND `reduce_only=True` AND the policy allows it, the order is let through (logged as a warning, not silent). Plumbed through `OrderRequest` (`routes_broker.py`), `TradeTool`, and all four genuinely risk-reducing call sites in `vinu-live`'s `orchestrator._submit_order` (50%-at-1R take-profit, allocator rebalance reduce, invalidation full close, contingency partial reduce); the one entry call site stays `reduce_only=False`. A naive "let all `sell` orders through" was rejected on purpose — a short entry is a `sell` that *increases* risk. Verified in code: `order_guard.py:76-115`. |
| **Existing component(s)** | `kill_switch.py`, `OrderGuard.check()`, `Monitor` breaker, `monitor-shock-exit.md` gap #1 |
| **Evidence** | `monitor-shock-exit.md` gap #1: "`HALT_ENTRIES` vs `HALT_ALL`. Block entries always on HALT. Allow risk-reducing exits on HALT. This is Row 12 kill policy undecided."<br>`kill_switch.py:100-109` — `is_trading_halted()` returns `True` for global halt, no scope for "allow exits".<br>`order_guard.py:86-87` — `if is_trading_halted(scope=symbol): return GuardResult(False, "Trading is halted by kill switch")` — **blocks all orders**.<br>`money-gate.md` kills: "HALT entries-only allow exits... Kill scope symbol vs global pinned. `order_guard.py` + `kill_switch.py` entries vs exits split... Risk-reducing always allowed."<br>**Confirmed independently**: `order_guard.py:check()` takes a `side` parameter, but the halt check at line 86 (`is_trading_halted(scope=symbol)`) fires unconditionally — no branch reads `side` to let a `sell`/risk-reducing order through. |
| **Status details** | **What exists now:**<br>• Kill switch works (filesystem-based, cross-process)<br>• Portfolio drawdown monitor triggers halt at -20%<br>• Scoped halts per symbol/strategy<br>• **`VINU_LIVE_HALT_POLICY=entries_only` is now honoured by *both* halt layers** — the local breaker and `OrderGuard`'s global-kill-switch check<br>• **Risk-reducing (`reduce_only`) orders pass a halt** at both layers; every `vinu-live` exit/reduce call site sets the flag<br><br>**Residual (not blocking):**<br>• The `reduce_only` flag on the LLM's own `submit_order` tool is available but the agent isn't yet prompted to set it — only `vinu-live`'s deterministic exit paths do (Stage 5 concern) |
| **Limitation** | A manual exit via the LLM `submit_order` tool during a halt still requires the caller to pass `reduce_only=true`; `vinu-live`'s automated exits do this already. |
| **Real-world consequence (now)** | Portfolio hits -20% → halt engages → `vinu-live`'s invalidation / contingency / take-profit exits and allocator-driven reduces all still execute → position can be closed / de-risked during the drawdown. |
| **Severity** | ~~CRITICAL — DANGEROUSLY MIS-HANDLED~~ → **RESOLVED (2026-09-09)**. Downgraded: automated risk-reducing orders survive a halt at both layers. |

---

## SCENARIO 22: DAILY RISK BUDGET — Informational Only, Not Enforced

| Field | Determination |
|-------|---------------|
| **Real-world scenario** | Symbol hits -3% daily P&L (TIER_HALT). `compute_risk_budget()` returns `suggested_size_multiplier: 0.0`. Next order for that symbol submitted. OrderGuard allows it (no check of risk budget). |
| **Trading phase** | Entry / Management |
| **Human failure** | Ignoring risk warnings; overriding risk limits |
| **Bot failure** | Risk budget computed but not enforced; OrderGuard doesn't read it |
| **Vina handling** | **✅ RESOLVED — fixed 2026-09-09 (Stage 2, how-to-make-it-live/CHANGES-2026-09-09.md)** |
| **Existing component(s)** | `vinu-portfolio` `compute_risk_status()`, `OrderGuard`, `live-safety/SKILL.md` |
| **Fix applied** | Two changes: (1) `OrderGuard._check_risk_budget()` now calls `GET /portfolio/risk/status` for every non-`reduce_only` order and rejects it if the symbol's `halted` flag is true (TIER_HALT) — reduce-only orders are explicitly exempt, same posture as the Scenario 21 kill-switch fix, so risk-reducing a halted symbol is still always allowed. Fails open on any lookup error, same convention as the existing `_check_portfolio_concentration`. (2) The `DailyPositionTracker` bug mentioned in the original evidence was real and separate: `vinu_portfolio/service.py`'s `compute_risk_status()` built a *fresh* tracker every call, so daily P&L never accumulated across polls. Moved the tracker onto the `PortfolioService` instance (constructed once, reused for the process lifetime) so accumulation is now real. A test that had explicitly asserted the broken non-accumulating behavior (`test_daily_pnl_does_not_accumulate_across_repeated_calls`) was rewritten to assert correct accumulation. |
| **Status details** | **What exists now:**<br>• 3-tier risk budget (warning -1%, reduce -2%, halt -3%) — unchanged, was already correct<br>• Tracker now persists across calls within a trading day (was resetting every call)<br>• OrderGuard rejects new/increasing orders for a TIER_HALT symbol, allows risk-reducing ones through<br><br>**Still not done:** no auto-halt of the *global* kill switch when a symbol hits TIER_HALT (this fix stops new orders for that one symbol via OrderGuard's own check, it doesn't escalate to `halt_trading(scope=symbol)`) — the two mechanisms could be unified in a later pass, but weren't required to close this scenario's specific failure mode. |
| **Real-world consequence (before the fix)** | Symbol loses -5% in a day; risk budget says "halt"; trader/agent submits order anyway; all guards pass; loss deepens |
| **Severity** | Downgraded from HIGH to **N/A (resolved)**. |

---

## SCENARIO 23: REBALANCE REQUEST — Capital Allocator Asks, Monitor Can Decline, No Force

| Field | Determination |
|-------|---------------|
| **Real-world scenario** | Capital allocator decides Strategy B (better calibration) should replace Strategy A (worse). Sends rebalance request to vinu-live. Monitor (TradePlanOrchestrator) declines because Strategy A is profitable (+5% gain protect). Capital allocator's decision ignored. |
| **Trading phase** | Portfolio management (rebalance) |
| **Human failure** | Not following rebalance discipline; protecting winners too long |
| **Bot failure** | Rebalance is advisory only; no enforcement; gain-protect can block necessary rotation |
| **Vina handling** | **✅ RESOLVED — `critical` override added 2026-09-09 (Stage 3, how-to-make-it-live/CHANGES-2026-09-09.md §S3-23)** |
| **Existing component(s)** | `capital_allocator_hook.py`, `rebalance_guard.py`, `vinu-live` `TradePlanOrchestrator`, `rebalance_intake.py` |
| **Fix applied** | `RebalanceRequest` gained `critical: bool` (dataclass + `rebalance_requests.critical` SQLite column via `SCHEMA_VERSION` 1→2 migration); `submit()` / `pending_for()` / `submit_rebalance_request()` / the `POST /trade-plan/rebalance-request` body all carry it. `_evaluate_rebalance_request` skips the `favorable_move_pct > 5%` decline when `request.critical` is set (logs a warning that it is overriding gain-protect). The breaker check, `reduce_only`, and the 50% reduce are unchanged — a `critical` request still cannot bypass a kill-switch HALT. |
| **Still open** | Gain-protect stays hardcoded at 5% for non-critical requests (not a configurable ladder); still no *timeline*/escalation if a non-critical request is repeatedly declined; the allocator must decide to set `critical` (no automatic "this rotation is overdue" trigger). |
| **Limitation** | The allocator can now force a reallocation through when it flags it critical; a normal request is still discretionary for the Monitor. |
| **Real-world consequence (now)** | The allocator marks the A→B rotation `critical: true`; the Monitor reduces Strategy A's position 50% despite it being +6.67%, instead of protecting it indefinitely. |
| **Severity** | ~~MEDIUM~~ → **RESOLVED** for the "no force" gap; the fixed 5% threshold for ordinary requests is a remaining nit, not a blocker. |

---

## SCENARIO 24: CONFIDENCE CALIBRATION — Only for trade_plan Artifacts, Not for Signal Strength

| Field | Determination |
|-------|---------------|
| **Real-world scenario** | TradePlan has `forecast: 0.65` (65% directional confidence). Position sized at full Kelly. Next day, same strategy generates forecast 0.52. Position sized same. No adjustment for lower confidence. |
| **Trading phase** | Entry (sizing) |
| **Human failure** | Sizing same regardless of conviction |
| **Bot failure** | No forecast-confidence → position-size mapping |
| **Vina handling** | **✅ RESOLVED — fixed 2026-09-09 (Stage 2, how-to-make-it-live/CHANGES-2026-09-09.md)** |
| **Existing component(s)** | `TradePlan` (forecast, p_failure), `position_sizing.py`, `orchestrator.py`'s `_maybe_enter`, `daily-allocation` (outcome multiplier) |
| **Fix applied** | Two consumers of forecast confidence, matching the two places a size actually gets decided in this codebase: (1) `vinu-agent/agent/position_sizing.py` gained `forecast_confidence_scale()` and a `forecast_confidence` parameter on `compute_position_size()`, applied as a multiplier alongside the existing CVaR/vol-target adjustments, default **on** (`VINU_RISK_FORECAST_SCALING_ENABLED=true`); (2) `vinu-live/trade_plan/orchestrator.py`'s `_maybe_enter()` — the actual live entry-sizing point for a TradePlan — now reads `plan["forecast"]["confidence"]` and applies the identical formula (duplicated locally, not imported, since these are separate deployable services) before computing `qty` from `risk_bands.max_position_size_pct`. Both floor the scale at 0.5 so a real forecast is dampened, never zeroed, by conviction alone; both treat missing/zero confidence as "no information" (no scaling) rather than a rejection. |
| **Status details** | **What exists now:**<br>• A 0.6-confidence TradePlan now enters at roughly 60% of its `risk_bands` max size (floored at 50%), not the full amount<br>• A 0.95-confidence plan enters close to its full approved size<br>• Configurable via `VINU_RISK_FORECAST_SCALING_ENABLED`/`_FLOOR` (both services read the same env var names)<br><br>**Still not done:** `p_failure` (a separate field, used only for invalidation) still isn't fed into sizing — this fix only wires `forecast.confidence`, which is what the scenario's own example used. `daily-allocation`'s outcome multiplier (historical calibration accuracy) remains a separate, unrelated mechanism — this fix is about *current* forecast confidence at entry time, not historical track record. |
| **Real-world consequence (before the fix)** | Low-conviction trades sized same as high-conviction; edge diluted; no dynamic sizing based on signal quality |
| **Severity** | Downgraded from MEDIUM to **N/A (resolved)**. |

---

## SCENARIO 25: MULTI-TIMEFRAME CONFLICT — 1H Strategy Long, 1D Strategy Short

| Field | Determination |
|-------|---------------|
| **Real-world scenario** | 1H sweep strategy signals LONG on AAPL. 1D sweep strategy signals SHORT on AAPL. Both promoted ACTIVE. Both get capital allocation. |
| **Trading phase** | Ongoing (portfolio) |
| **Human failure** | Ignoring timeframe conflict; netting positions mentally |
| **Bot failure** | No timeframe-aware conflict detection; sleeves not implemented |
| **Vina handling** | **NOT HANDLED** |
| **Existing component(s)** | `capital_allocator` (budget per interval?), `daily-allocation`, `VINU_SWEEP_INTERVALS` |
| **Evidence** | `money-gate.md` — "Future timeframe: same `VINU_SWEEP_INTERVALS` drives gate per interval, no extra knob. 15min gate same thresholds + fills honest required."<br>`daily-allocation/SKILL.md:177-187` — on-demand only, not scheduled per interval.<br>`money-gate.md` gap #4 — "sleeves 1D/1H separate" — **not built**. |
| **Status details** | **What exists:**<br>• `VINU_SWEEP_INTERVALS` knob for multiple timeframes<br>• Separate sweep runs per interval<br><br>**What's missing:**<br>• **No sleeve separation** — 1D and 1H positions commingled in same portfolio<br>• **No cross-timeframe conflict detection**<br>• **No netting logic** — long 1H + short 1D = flat but double costs<br>• **No timeframe-aware allocation** — single budget across all intervals |
| **Limitation** | Multi-timeframe strategies operate in **same portfolio namespace** with no isolation. |
| **Real-world consequence** | 1H long + 1D short = net flat, paying 2x commissions/slippage; or both long with different horizons/exits; no coherent management |
| **Severity** | **HIGH** — Documented as "sleeves 1D/1H separate" in money-gate; not implemented |

---

## SCENARIO 26: TAX / BORROW / DIVIDEND DRAG — Short Positions Cost More Than Modeled

| Field | Determination |
|-------|---------------|
| **Real-world scenario** | Short position held 60 days. Borrow rate 15% annual (hard-to-borrow). Dividend paid (short owes dividend). Short-term capital gains tax 37% vs long-term 20%. Sim modeled none of these. |
| **Trading phase** | Ongoing (carry) / Exit (tax) |
| **Human failure** | Ignoring carry costs; not modeling tax drag |
| **Bot failure** | Sim ignores borrow, dividends, tax; P&L gross not net |
| **Vina handling** | **NOT HANDLED** |
| **Existing component(s)** | `vinu-simulator` (costs.py), `money-gate.md` gap #8 |
| **Evidence** | `money-gate.md` gap #8: "Shorts pay borrow daily, shorts owe dividends, splits adjust qty price overnight, taxes short-term vs long-term cut net 20-30 percent. Sim no borrow, no dividend owe, no tax haircut. Paper gross overstates kept."<br>Knobs defined: `VINU_EXEC_BORROW_RATE`, `VINU_EXEC_CORP_ACTION_CHECK`, `VINU_NET_TAX_HAIRCUT_SHORT=0.7`, `VINU_NET_TAX_HAIRCUT_LONG=0.85` — **not implemented**. |
| **Status details** | **No mechanism for:**<br>• Borrow rate per symbol (hard-to-borrow)<br>• Dividend calendar check before short entry<br>• Split adjustment before entry<br>• Net-after-tax view (0.7x gross short-term, 0.85x long-term)<br>• Paper Sharpe gross + net columns |
| **Limitation** | Simulation is **gross-only**. Live net can be 30-50% lower for short strategies. |
| **Real-world consequence** | Short strategy shows Sharpe 1.5 gross; net Sharpe 0.7 after borrow/dividend/tax; live fails expectations |
| **Severity** | **HIGH** — Money-gate gap #8; silent P&L destroyer |

---

## SCENARIO 27: IDEMPOTENCY — Double Fill on Retry

| Field | Determination |
|-------|---------------|
| **Real-world scenario** | Order submitted. Network timeout. Agent retries. Both orders fill. Position 2x intended size. |
| **Trading phase** | Entry |
| **Human failure** | Not using idempotency keys; retrying blindly |
| **Bot failure** | No idempotency key generation/validation |
| **Vina handling** | **✅ RESOLVED — verified 2026-09-09** (originally NOT HANDLED) |
| **Verified** | `orchestrator.py:777-792` — every order submission now generates `client_order_id = f"{artifact}-{symbol}-{side}-{qty}-{minute_bucket}"`, gated by `VINU_EXEC_IDEMPOTENCY_ENABLED` which **defaults to true**. A retry within the same minute dedupes on the broker rather than double-filling. Rating: **8/10** — real fix, on by default; minute-bucket granularity is the only residual edge case (a retry issued >60s after the original could still double-fill). |
| **Existing component(s)** | `trade_tool.py`, `money-gate.md` gap #5 |
| **Evidence** | `money-gate.md` gap #5: "idempotency double fill... Fix: idempotency key artifact+cycle+slice."<br>`trade_tool.py` — no idempotency key in `OrderRequest` or `submit_order`. |
| **Status details** | **No mechanism for:**<br>• Idempotency key generation (artifact_id + cycle + slice)<br>• Broker-side idempotency (Alpaca supports `client_order_id`)<br>• Duplicate detection on retry |
| **Limitation** | Retry logic exists (HTTP retry 10s×3) but **no idempotency protection**. |
| **Real-world consequence** | Network glitch → double position → 2x risk → potential margin call |
| **Severity** | **HIGH** — Explicitly documented gap; simple fix but not done |

---

## SCENARIO 28: RESTART WIPE — Container Restart Loses Paper State

| Field | Determination |
|-------|---------------|
| **Real-world scenario** | Paper trading running 5 days. Container restarts (deploy, crash, update). Paper positions, P&L, calibration state lost. Restarts from zero. |
| **Trading phase** | Operational |
| **Human failure** | Not persisting paper state; assuming container persistence |
| **Bot failure** | Paper state in memory/tmpfs; not in persistent volume |
| **Vina handling** | **✅ RESOLVED — verified 2026-09-09** (originally NOT HANDLED) |
| **Verified** | `vinu-live` writes its position book (`trade_plan_book.db`) under `VINU_LIVE_DATA_ROOT`, which `docker-compose.yml`'s `live-api` service bind-mounts to the host directory `./data/live` — not tmpfs. The tmpfs reference the original gap doc cited (`/nonexistent:rw,mode=1777,exec`) belongs to the unrelated `agent-api` scratch mount, not the live paper book. Rating: **9/10** — restart does not lose the book; only residual risk is anything genuinely written to `/tmp` inside `live-api`'s container, which the service's own tmpfs mounts (`/tmp`, `/home/app/.cache`) would still wipe — but the book itself isn't there. |
| **Existing component(s)** | `docker-compose.yml`, `vinu-live` paper trading, `money-gate.md` gap #5 |
| **Evidence** | `money-gate.md` gap #5: "restart wipes paper before fix".<br>`22-infra/plan.md` — "agent tmpfs /nonexistent:rw,mode=1777,exec" — agent uses tmpfs (ephemeral). |
| **Status details** | **No mechanism for:**<br>• Persistent paper trading state (positions, P&L, calibration)<br>• Survival across container restarts<br>• `VINU_AGENT_DATA_ROOT=/data` is bind-mounted but paper state not written there |
| **Limitation** | Paper trading state is **ephemeral**. Restart = reset. |
| **Real-world consequence** | 10-day paper validation reset on deploy; promotion decision based on incomplete paper track record |
| **Severity** | **HIGH** — Money-gate requires 10d paper; restart breaks it |

---

## SCENARIO 29: SECRETS LEAK — API Keys in Plaintext

| Field | Determination |
|-------|---------------|
| **Real-world scenario** | Docker image inspected. `.env` file or environment variables contain Alpaca keys, Polygon keys, LLM keys in plaintext. |
| **Trading phase** | Operational / Security |
| **Human failure** | Committing secrets; not using secret management |
| **Bot failure** | No secret rotation; no vault integration |
| **Vina handling** | **PARTIALLY HANDLED** |
| **Existing component(s)** | `22-infra/plan.md`, `secrets_loader.py`, `setup-secrets.sh` |
| **Evidence** | `22-infra/plan.md` — "Secrets check + .env hygiene (URLs only, keys in files). Retry: allocator pattern... Dockerfile slim... Acceptance: --check ready, no plain leak in inspect."<br>`secrets_loader.py:44` — fallback warning. |
| **Status details** | **What exists:**<br>• `secrets_loader.py` loads from files<br>• `setup-secrets.sh --check` validates<br>• Dockerfile improvements in progress<br><br>**What's missing:**<br>• **No vault/secret manager integration** (AWS Secrets Manager, HashiCorp Vault, etc.)<br>• **No automatic rotation**<br>• **No audit of secret access** |
| **Limitation** | Secrets in files (better than env) but **no enterprise secret management**. |
| **Real-world consequence** | Image leak → API keys compromised → unauthorized trading → financial loss |
| **Severity** | **MEDIUM** — In progress (22-infra); not production-grade |

---

## SCENARIO 30: "I DON'T KNOW" — System Recognizes Insufficient Information

| Field | Determination |
|-------|---------------|
| **Real-world scenario** | Unprecedented market event (flash crash, COVID-style). No historical analog. Regime unknown. Signals conflicting. Data stale. Correct decision: **do nothing / reduce to flat**. |
| **Trading phase** | All phases |
| **Human failure** | Forcing a decision; overconfidence in model |
| **Bot failure** | No "uncertainty quantification" → "no trade" pathway; always produces an answer |
| **Vina handling** | **NOT HANDLED** |
| **Existing component(s)** | `AgentLoop` (LLM reasoning), `governor` (heuristics), `readiness_score` (game plan) |
| **Evidence** | `governor/SKILL.md` — Layer 2 heuristics (progress, expectancy) for *search stopping*, not *trading decisions*.<br>`daily-allocation/SKILL.md:208-234` — `readiness_score` reflects data availability (regime, equity, plans) but **only gates game plan trustworthiness**, not trading.<br>`AgentLoop` — LLM can say "I don't know" but no structured uncertainty → no-trade pipeline. |
| **Status details** | **No mechanism for:**<br>• Quantified uncertainty (epistemic vs aleatoric)<br>• "Confidence interval on forecast" → position size = 0 if too wide<br>• "Regime unknown" → reduce all positions<br>• "Data stale" → pause trading<br>• "Signals conflict" → do nothing<br>• Explicit "I don't know" → flat portfolio |
| **Limitation** | System **always produces an action** (allocation, order, hold). No "uncertainty → inaction" pathway. |
| **Real-world consequence** | Black swan event → system trades anyway based on stale/conflicting signals → catastrophic loss |
| **Severity** | **CRITICAL** — Most sophisticated systems fail here; Vina has no "unknown" state |

---

## SCENARIO 31: MODEL DISAGREEMENT — LLM vs Quantitative Signal vs Human

| Field | Determination |
|-------|---------------|
| **Real-world scenario** | Quantitative signal: BUY. LLM research: SELL (fundamental deterioration). Human trader: HOLD (waiting for clarity). Three-way conflict. |
| **Trading phase** | Before Entry / Management |
| **Human failure** | Picking the view that confirms bias |
| **Bot failure** | No multi-source conflict resolution; no weighted consensus |
| **Vina handling** | **NOT HANDLED** |
| **Existing component(s)** | `AgentLoop` (LLM), `strategy-research` skill, `TradePlan`, `capital_allocator` |
| **Evidence** | `strategy-research/SKILL.md` — LLM-driven research loop.<br>`TradePlan` — LLM-authored forecast/invalidation.<br>`capital_allocator` — LLM manager decides funding.<br>No component compares quantitative signal vs LLM forecast vs human input. |
| **Status details** | **No mechanism for:**<br>• Multi-source signal aggregation<br>• Conflict detection across signal types (quant vs LLM vs human)<br>• Weighted consensus (quant 60%, LLM 30%, human 10%)<br>• "Disagreement = reduce size" logic |
| **Limitation** | Each signal path operates independently. Conflicts resolved only by **who submits the order last**. |
| **Real-world consequence** | Quant buys while LLM sells; offsetting positions; capital wasted; no coherent thesis |
| **Severity** | **HIGH** — Multi-modal systems need conflict resolution; Vina has none |

---

## SCENARIO 32: POST-TRADE LEARNING — Does Vina Actually Learn?

| Field | Determination |
|-------|---------------|
| **Real-world scenario** | Trade closed. Win or loss. System should update: strategy calibration, position sizing, regime models, correlation estimates. |
| **Trading phase** | Post-trade |
| **Human failure** | Not reviewing trades; not updating models |
| **Bot failure** | Learning loop broken or incomplete |
| **Vina handling** | **PARTIALLY HANDLED** |
| **Existing component(s)** | `FeedbackLoopWorker` (vinu-live), `calibration_entries`, `daily-allocation` outcome multiplier, `20-learning` |
| **Evidence** | `daily-allocation/SKILL.md:102-108` — "`vinu-live`'s `FeedbackLoopWorker` posts every closed position's realized return to `POST .../record-outcome` when it has an `artifact_id`."<br>`20-learning/plan.md` — learning over time planned.<br>`live-safety/SKILL.md:162-163` — "calibration track-record... is a weaker proxy for 'has this strategy been checked against reality since promotion'." |
| **Status details** | **What exists:**<br>• `FeedbackLoopWorker` records realized outcomes for `trade_plan` artifacts<br>• Calibration accuracy → outcome multiplier in daily allocation<br>• `20-learning` step planned for regime/feature learning<br><br>**What's missing:**<br>• **No learning for YAML strategies** (gap #20)<br>• **No position sizing learning** — Kelly fraction not updated from realized outcomes<br>• **No regime model learning** — regime classification static thresholds<br>• **No correlation model learning** — DCC-GARCH re-estimated but not validated<br>• **No feature importance learning** — which features predicted outcomes? |
| **Limitation** | Learning exists **only for trade_plan calibration accuracy**. Everything else static. |
| **Real-world consequence** | Strategy edge decays; system doesn't adapt; sizing stays same; regime thresholds wrong; correlation models stale |
| **Severity** | **HIGH** — Adaptive system needs learning; Vina has minimal |

---

## SCENARIO 33: UNPRECEDENTED MARKET BEHAVIOR — Outside Training/Backtest Distribution

| Field | Determination |
|-------|---------------|
| **Real-world scenario** | Market does something never in 20-year backtest: VIX 80, 10% intraday moves, correlation 1.0 across all assets, liquidity vanishes. |
| **Trading phase** | All phases |
| **Human failure** | Applying normal rules to abnormal conditions |
| **Bot failure** | No "out-of-distribution" detection; no emergency mode |
| **Vina handling** | **HANDLED (response side), 2026-09-09, Stage 4 `#33`** — manual emergency-flatten **and** a dormant auto-detector that fires it. Residual: the detector uses only the book's own price history, no market-wide vol feed. |
| **Existing component(s)** | `shock_correlation.py` (crisis_correlation), `Monitor` shock clustering, `kill_switch`, **`orchestrator.emergency_flatten()` + `/live/trade-plan/emergency-{flatten,resume,status}` (new)** |
| **Evidence** | `shock_correlation.py` — DCC-GARCH estimates crisis correlation.<br>`Monitor` — shock clustering triggers off-cycle check.<br>**Fill applied (2026-09-09):** `orchestrator.py` `emergency_flatten()` sets the agent's global kill switch (all services) **and** reduce_only-closes every open book position; `emergency_resume()` lifts it; `_maybe_enter` refuses entries via `entry_blocked_by_emergency_halt` while the mirror flag is set (refreshed each cycle from `/agent/broker/status`). CHANGES §S4-33. |
| **Status details** | **What exists now:**<br>• Crisis correlation detection (DCC-GARCH)<br>• Shock clustering trigger<br>• Kill switch (portfolio DD -20%) — with a reduce_only exemption so exits pass (Scenario 21 fix)<br>• **One-call emergency FLATTEN** — halt every service + market-close every position, `POST /live/trade-plan/emergency-flatten`; deliberate `emergency-resume` to undo<br>• **Automatic OOD detector** (`_check_ood`, per cycle) — 3 signals (mean pairwise correlation ≥ 0.95, mean realized-vol ≥ 0.08/day, any held name's 1-day move ≥ 10%); fires when ≥2 trip together; **ships dormant**, graduated `off → alert → halt → flatten`, latched to act once<br>• Runtime pairwise-correlation de-risk (Scenario 12 fix)<br><br>**Still open:**<br>• Detector inputs are the **book's own price history** only — no market-wide VIX/vol feed, so a broad-market dislocation the book hasn't felt yet is invisible until it does<br>• Auto-mode ships `off`; the operator has to earn it up to `flatten` by observing `alert`/`halt` in paper<br>• Liquidity-crisis auto-mode still partial (the spread gate #13 blocks *entries* only) |
| **Limitation** | There is now a full **shock response**: a detector that fires an exit-safe (reduce_only) flatten of the whole book, plus the same as a manual one-call command. The auto-path is dormant by default and must be graduated into `flatten` after paper observation — deliberately, because a false-positive auto-flatten liquidates everything. |
| **Real-world consequence** | A 2020-March / Flash-Crash-style event: with the detector at `flatten` it dumps the book and halts on the first cycle where ≥2 signals trip; at `alert`/`off` an operator still has the one-call button and it will get the exits out. |
| **Severity** | **CRITICAL → reduced** — a real, automated emergency protocol now exists; it stays rated high only because activation is deliberately gated and the detector has no external-vol input. |

---

## SCENARIO 34: CONFIDENCE/UNCERTAINTY PROPAGATION — Research → Allocation → Execution

| Field | Determination |
|-------|---------------|
| **Real-world scenario** | Research: deflated Sharpe 0.95 (barely passes), holdout pass, PBO 0.45. Promotion: ACTIVE. Allocation: full weight (regime bull, outcome neutral). Execution: full size. No uncertainty propagated. |
| **Trading phase** | End-to-end |
| **Human failure** | Treating marginal promotion as high confidence |
| **Bot failure** | Binary promotion → binary allocation → binary sizing; no confidence gradient |
| **Vina handling** | **⚠️ PARTIALLY HANDLED — upgraded from DANGEROUSLY MIS-HANDLED 2026-09-09 (Stage 2, how-to-make-it-live/CHANGES-2026-09-09.md)** |
| **Existing component(s)** | `promotion.py`, `daily-allocation` (now `_confidence_gradient_multiplier`), `position_sizing.py` (now `forecast_confidence` — see Scenario 24), `capital_allocator` |
| **Fix applied** | `vinu-portfolio`'s `compute_daily_allocation()` gained a third bounded multiplicative tilt, `_confidence_gradient_multiplier()`, alongside the existing `regime_multiplier`/`outcome_multiplier`: maps a strategy's `deflated_sharpe` position within `[promotion_deflated_sharpe_threshold, 1.0]` (deflated Sharpe is itself a probability bounded to 1.0, not an unbounded ratio despite the name — the original scenario's own "0.95 vs 2.0" example was off the metric's real scale) to the same `±confidence_tilt_bound` (default 0.3) band the other two tilts already use. A bare pass (deflated Sharpe at the threshold) now gets 0.7x; a strategy at the metric's ceiling (1.0) gets 1.3x; linear in between. `deflated_sharpe` is now propagated through `list_active_strategies()`'s in-process AND HTTP paths (it was silently dropped by both before this fix, same class of bug as Scenario 20's routes). Separately, Scenario 24's forecast-confidence-scaling fix addresses a related but distinct axis: per-trade forecast conviction at entry-sizing time, not strategy-level promotion margin. |
| **Status details** | **What's now handled:** deflated-Sharpe margin above the promotion bar now genuinely tilts allocation weight — a 0.951 and a 0.999 strategy no longer get identical sizing.<br><br>**Still NOT handled:** **PBO margin has no gradient** — Scenario 19's fix made PBO a hard threshold check at promotion (reject above 0.7), but a strategy at PBO 0.1 and one at PBO 0.65 (both under threshold, very different overfitting risk) still get the same allocation weight; **binary promotion gate itself is unchanged** — `promotion.py`'s `PromotionVerdict` is still eligible/not, the cliff effect at the threshold boundary (0.949 rejected vs 0.951 admitted) still exists, this fix only affects what happens to weight *after* a strategy is already admitted; **no "probationary" sizing** — a freshly promoted strategy with zero live track record gets the same confidence-gradient treatment as one that has been ACTIVE and performing well for months (outcome_multiplier is separate and only kicks in once calibration/track-record data exists). |
| **Limitation** | Confidence propagates from research into allocation for one specific signal (deflated Sharpe margin) that previously propagated for none. PBO margin, the promotion gate's binary nature itself, and probationary sizing for new promotions remain open — this scenario is now genuinely PARTIALLY HANDLED, not DANGEROUSLY MIS-HANDLED, but not fully resolved. |
| **Real-world consequence** | Reduced but not eliminated: a bare-pass strategy now gets less capital than a strong-pass one (the original scenario's core complaint), but a low-but-under-threshold PBO strategy still gets full weight, and newly promoted strategies still aren't sized more conservatively just for being new |
| **Severity** | Downgraded from CRITICAL/DANGEROUSLY MIS-HANDLED to **MEDIUM (partially handled)** — the false-equivalence problem for deflated Sharpe is closed; the same problem for PBO margin, and the binary-cliff/no-probationary-sizing issues, remain. |

---

## SCENARIO 35: POSITION LIFECYCLE STATE CONSISTENCY — What Does Vina Think It Holds?

| Field | Determination |
|-------|---------------|
| **Real-world scenario** | Partial fill → residue cancelled → position 200 shares. Broker shows 200. Vina book shows 1000 (intended). Monitor checks invalidation on 1000. OrderGuard checks concentration on 1000. Reality: 200. |
| **Trading phase** | Management |
| **Human failure** | Not reconciling; trusting internal book |
| **Bot failure** | Book/broker reconciliation only every 90s; no intra-cycle sync |
| **Vina handling** | **PARTIALLY HANDLED** |
| **Existing component(s)** | `Monitor` reconciliation (`orchestrator.py:658`), `OrderGuard` (uses broker `get_account`/`get_positions`), `vinu-live` book |
| **Evidence** | `monitor-shock-exit.md` — "Reconciles book vs broker every cycle. File `orchestrator.py:658`."<br>`order_guard.py:124-131` — uses `broker.get_account()` for equity (real-time).<br>`trade_tool.py` — returns broker response with actual fill. |
| **Status details** | **What exists:**<br>• OrderGuard uses **live broker data** for equity/position checks (real-time)<br>• Monitor reconciles **every 90s**<br>• TradeTool returns actual broker fill status<br><br>**What's missing:**<br>• **No intra-cycle reconciliation** — 90s gap where book ≠ broker<br>• **No partial fill handling** — book not updated on partial fill (Scenario 15)<br>• **No residue tracking** — cancelled/unfilled not in book<br>• **OrderGuard checks concentration on broker positions** (good) but **Monitor checks invalidation on book positions** (may differ) |
| **Limitation** | **Two sources of truth** (book vs broker) with 90s sync. OrderGuard uses broker (correct); Monitor uses book (stale). |
| **Real-world consequence** | Monitor fails to exit (book shows position OK); broker position actually underwater; or Monitor exits based on book but broker position already closed |
| **Severity** | **HIGH** — Inconsistent state between components |

---

## SCENARIO 36: SIGNAL AGING — TradePlan Generated, Not Acted On, Market Moves

| Field | Determination |
|-------|---------------|
| **Real-world scenario** | TradePlan generated at 9:30 AM. Entry zone $150-151. 10:00 AM: price $155. TradePlan still "valid" per invalidation conditions (not hit). But signal is stale — momentum entry missed. |
| **Trading phase** | Before Entry |
| **Human failure** | Acting on stale signal; not recognizing signal expiration |
| **Bot failure** | No signal TTL; no "signal age" in TradePlan; invalidation conditions don't include time |
| **Vina handling** | **✅ RESOLVED — fixed 2026-09-09 (Stage 2, how-to-make-it-live/CHANGES-2026-09-09.md)** |
| **Existing component(s)** | `TradePlan` (`created_at`, invalidation_conditions), `trade_plan_authoring.py`, `orchestrator.py`'s `_maybe_enter` |
| **Fix applied** | The original claim of "no `signal_generated_at` field" turned out to be only half true: `TradePlan.created_at` already existed on the dataclass and was already being stamped with a real timestamp at generation time in the actual production authoring path (`trade_plan_authoring.py`'s `author_trade_plan()` → `TradePlan(..., created_at=datetime.now(timezone.utc).isoformat())` → `freeze_trade_plan()` persists it into `Artifact.trade_plan_data`) — the data existed, nothing downstream read it. Added `_signal_age_hours()` to `orchestrator.py` and a `SIGNAL_MAX_AGE_HOURS` check (env `VINU_LIVE_SIGNAL_MAX_AGE_HOURS`, default 72h) in `_maybe_enter()`: a plan whose `created_at` is older than the threshold is now rejected with `entry_blocked_by_stale_signal` instead of being entered as if freshly generated. Fails open (never blocks) on a missing or unparseable `created_at`. |
| **Status details** | **What exists now:**<br>• A 3-day-old (default threshold) untriggered plan is now rejected at entry time, logged with its exact age<br>• Configurable per deployment via `VINU_LIVE_SIGNAL_MAX_AGE_HOURS`<br><br>**Still not done:** no "signal age" penalty on confidence/sizing for signals that are old but still within the TTL window (a plan at hour 71 of a 72h window sizes identically to one at hour 1) — only a hard cutoff, not a graduated decay. No proactive alert ("TradePlan aged > 4 hours — re-evaluate") before the cutoff is hit. |
| **Limitation** | TradePlan is now **valid for a window**, not valid-until-invalidated forever — the core claim of the scenario. The window is a hard cutoff, not a graduated confidence decay. |
| **Real-world consequence (before the fix)** | Chasing stale setups; entering at worse prices; invalidation conditions designed for entry zone, not aged signal |
| **Severity** | Downgraded from MEDIUM to **N/A (resolved)**. |

---
---

# SUMMARY: VINA REAL-WORLD SCENARIO COVERAGE

---

### A. STRONGLY HANDLED SCENARIOS (Vina is genuinely robust)

| # | Scenario | Why It Works |
|---|----------|--------------|
| 1 | **Structurally invalid orders blocked** | OrderGuard: kill switch, mandate limits, active artifact, market hours, concentration — all enforced at order time with fail-closed on kill switch, fail-open on service errors |
| 2 | **Portfolio drawdown circuit breaker** | `PortfolioDrawdownMonitor` + `drawdown_scheduler` running live; polls equity every interval; halts via kill switch at -20% DD; confirmed end-to-end |
| 3 | **Kill switch cross-process mutual exclusion** | Filesystem-based with `fcntl.flock`; `halt_trading()`/`resume_trading()` share lock with `OrderGuard.pre_approve()` and `capital_allocator_hook`; genuine mutual exclusion |
| 4 | **Daily order/volume caps per symbol** | SQLite-backed `DailyLimitStore` survives process restarts; enforced in `OrderGuard.check()` and `pre_approve()` |
| 5 | **Bracket orders at entry** | `TradeTool` supports `take_profit_price` + `stop_loss_price` → real resting orders at broker; not manual follow-up |
| 6 | **Shock-triggered monitor check** | Off-cycle check on shock clustering; debounce 60s; batch top 5 by shock score |
| 7 | **Promotion statistical gate** | Deflated Sharpe + holdout + stress test + correlation gate — all hard at promotion; `force=true` only for human override |
| 8 | **Risk-parity allocation with regime/outcome tilts** | `compute_daily_allocation()`: base weight × regime × outcome; bounded ±30%; readiness score gates trustworthiness |
| 9 | **DCC-GARCH crisis correlation** | Portfolio-level time-varying correlation; `crisis_correlation`, `shock_delta`, `shock_count` computed |
| 10 | **Audit logging every order** | `AuditLogger` writes structured JSONL to persistent volume; every order rejected/executed/filled logged |

**Common thread**: everything in this column is a **structural, order-time, or scheduled** control — something that runs on a fixed cycle or fires deterministically on a threshold with no interpretation required. Vina is strong wherever "strong" means "mechanical and unconditional."

---

### B. PARTIALLY HANDLED SCENARIOS (Meaningful protection but weaknesses)

| # | Scenario | Handles | Misses |
|---|----------|---------|--------|
| 1 | FOMO entry | Structural guards (artifact, size, limits) | No behavioral detection (urgency, chasing, thesis completeness) |
| 4 | Volatility increase mid-trade | Monitor checks invalidation every 90s + shock trigger | No vol-scaled stops, no default trailing, no time-stop, no thesis-weakening detection |
| 6 | Regime change mid-trade | Daily allocation adjusts future weights; shock correlation detects | No intra-trade regime action; fail-open regime; vocabulary mismatch |
| 8 | Overtrading | Per-symbol order/volume caps, throttle | No portfolio-level turnover cap; no cost-aware sizing |
| 10 | Stop-loss behavior | Bracket orders at entry; monitor checks invalidation | No stop quality classification; no adaptive stops; no learning from stops |
| 11 | Thesis vs market noise | Explicit invalidation conditions; p_failure probability | Binary invalidation; no regime-relative; no "thesis intact" override |
| 12 | Correlated positions | Order-time correlation/concentration check; daily crisis correlation | No runtime correlation monitor; no auto-de-risking; sleeves not built |
| 14 | System outage | Kill switch independent of broker; fail-open on errors | No fallback broker; no stale-data pause; single point of failure |
| 16 | Data staleness | Robust ingest pipeline with retry/gap validation | No freshness SLA; nothing blocks trading on stale data |
| 17 | Position sizing | Quarter-Kelly + fallbacks; vol-target cap; concentration headroom | No CVaR gate; no dynamic vol targeting; no DD-halve; point-estimate Kelly |
| 22 | Daily risk budget | 3-tier computed with regime multiplier | **Not enforced** — advisory only; OrderGuard doesn't read it; tracker broken in prod |
| 23 | Rebalance | Capital allocator requests; kill switch guard | Monitor can decline (gain-protect); no enforcement; advisory only |
| 29 | Secrets | File-based loading; setup check | No vault; no rotation; no audit |
| 32 | Post-trade learning | Calibration accuracy for trade_plan → allocation tilt | Only for trade_plan; no sizing/regime/correlation learning; YAML strategies zero |
| 35 | Position state consistency | OrderGuard uses live broker; Monitor reconciles 90s | 90s gap; partial fills not in book; two sources of truth |

**Common thread**: the *measurement* exists — the number gets computed correctly — but the *action* that should follow from the number either doesn't fire, fires too late (only at the next scheduled cycle), or only prevents *new* orders rather than adjusting *existing* positions.

---

### C. COMPLETELY UNCOVERED SCENARIOS (No meaningful mechanism)

| # | Scenario | Gap |
|---|----------|-----|
| 2 | **Event risk (earnings, FDA, corporate actions, borrow spikes)** | ~~No calendar check~~ → **earnings + US-macro blackout added 2026-09-09** (`/stock/events`, `VINU_LIVE_EVENT_BLACKOUT_HOURS`, Stage 4 `#2`); still no borrow-rate feed, no FDA/ad-hoc catalyst calendar |
| 3 | **Conflicting signals (same symbol, multiple strategies)** | No conflict detection; no resolution rule; offsetting positions possible and invisible as such |
| 5 | **New signal contradicts an already-open position** | Monitor only re-checks the frozen invalidation conditions on the position it opened; it never re-runs or listens to other strategies' live signals |
| 7 | **Revenge trading (2 losses → immediate re-entry)** | Explicitly documented as unbuilt; only a 60s debounce exists, not a loss-count cooldown |
| 9 | **Hesitation on a valid signal (missed entry)** | No signal TTL, no tracking of "generated but not acted on," no real-time nudge |
| 13 | **Liquidity disappearing (spread widens 10x, no fills)** | ~~No liquidity/spread monitoring~~ → **entry-side spread gate added 2026-09-09** (`VINU_LIVE_MAX_SPREAD_BPS`, Stage 4 `#13`); still no exit-side gate (by design), no dynamic order-type switching, fixed slippage model |
| 15 | **Partial fill leaves an unintended position size** | No fill-state tracking; risk checks continue to assume the intended size, not the actual size |
| 19 | **PBO computed but not persisted** | Overfitting score vanishes after the research call returns; cannot be checked at promotion time |
| 20 | **YAML strategies have zero outcome tracking** | 4 built-in strategies get a permanent neutral allocation weight no matter how they perform |
| 24 | **Forecast confidence disconnected from position size** | `forecast` field exists on every TradePlan but sizing code never reads it |
| 25 | **Multi-timeframe strategies conflict (1H long vs 1D short)** | No sleeve separation; same symbol across timeframes shares one portfolio namespace |
| 26 | **Tax / borrow / dividend drag on short positions** | Simulation and paper P&L are gross-only; live net can run 20-50% lower with zero warning |
| 27 | **Idempotency — retry causes a double fill** | No idempotency key anywhere in the order-submission path |
| 28 | **Container restart wipes paper-trading state** | Paper positions/P&L live in ephemeral storage; a redeploy resets the 10-day validation clock to zero |
| 30 | **"I don't know" — system always produces an action** | No uncertainty-to-inaction pathway; conflicting/stale/absent information still yields a trade decision |
| 31 | **Quant signal vs LLM research vs human disagree** | Whichever order is submitted last wins; no aggregation, no size reduction on disagreement |
| 33 | **Market behaves outside anything in the backtest distribution** | ~~no emergency-flatten response, no OOD trigger~~ → **DONE 2026-09-09** (Stage 4 `#33`): manual `/live/trade-plan/emergency-flatten` (halt every service + reduce_only-close every position, exit-safe) **and** an automatic `_check_ood` detector (3 signals, ≥2-of-3, ships dormant, graduated `off→alert→halt→flatten`). Residual: detector uses book price history only, no external vol feed. |
| 36 | **Signal aging — a TradePlan stays "valid" indefinitely if untriggered** | No `valid_until`/`max_age` field; a 3-day-old setup with no fill is still actionable |

**Common thread**: these are not weaknesses in an existing mechanism — there is genuinely **no code path** that reasons about the situation at all. If one of these happens, the system's behavior is whatever falls out of components built for a different purpose (e.g., a stale TradePlan just sits there because nothing was ever built to expire it), not a deliberate decision.

---

### D. UNKNOWN AREAS (Insufficient evidence in the implementation to determine handling)

The 36-scenario sweep above was thorough enough that almost every scenario landed a definite verdict. The genuine "unknowns" are narrower — places where a knob or partial implementation exists but its actual runtime behavior wasn't traced end-to-end in either session:

| Area | Why it's unknown |
|------|-------------------|
| **`VINU_BROKER_FALLBACK_URL` / `VINU_OUTAGE_PAUSE_ENTRIES` (Scenario 14)** | Documented as "knob defined" in `money-gate.md`, but neither session confirmed whether these env vars are read anywhere in code or are pure documentation placeholders. **UNKNOWN — insufficient evidence in the existing implementation.** |
| **What happens to an in-flight LLM agent decision if the process is killed mid-reasoning** | No component was traced for agent-loop crash recovery / resumability. **UNKNOWN.** |
| **Whether `readiness_score` (Scenario 30) is ever consulted outside the "game plan" display, e.g. by the capital allocator before funding** | Only its computation was traced (`daily-allocation/SKILL.md:208-234`); its consumers were not fully enumerated. **UNKNOWN.** |
| **Whether `HistoricalFillBroker` vs live Alpaca broker diverge on partial-fill reporting** | Only Alpaca-path gaps were documented (`16-broker-fills.md`); the simulator's partial-fill semantics weren't separately confirmed. **UNKNOWN.** |
| **Multi-broker / secondary environment readiness** referenced in `22-infra/plan.md` | Described as "in progress"; current completion state wasn't verified against code, only against planning docs. **UNKNOWN.** |

Do not assume any of these behave safely merely because a related knob or plan document exists — that is precisely the failure mode Section E covers next.

---

### E. DANGEROUS ASSUMPTIONS (You might believe Vina handles this — it doesn't, end-to-end)

These are the highest-priority section for you specifically, because they're the gap between what the *codebase suggests* and what *actually executes*:

1. ~~"ShadowEvaluator paper-checks every promotion" — false.~~ **RESOLVED, was a verification error on my part.** `entrypoint.sh` does schedule it (`vinu-live shadow-worker &`); I'd only checked `scheduler.py` and missed the actual entrypoint. (Scenario 18)
2. **"The kill switch protects me in a crash" — was half false, now fixed.** It used to stop you from *reducing* risk on positions you already hold, at exactly the moment reducing risk matters most, because `order_guard.py`'s halt check ignored `side`. **Fixed 2026-09-09**: `OrderGuard.check()` now takes a `reduce_only` flag, exempted from the halt under the same `VINU_LIVE_HALT_POLICY=entries_only` policy vinu-live's local breaker already used — plumbed through `pre_approve()`, `TradeTool`, `OrderRequest`, and all four of vinu-live's exit/reduce call sites. (Scenario 21)
3. **"The risk budget system will stop me from overtrading a losing symbol" — was false, now fixed.** `compute_risk_budget()` computed the right tier (warning/reduce/halt), and a separate bug meant the underlying daily P&L tracker never accumulated across calls. **Fixed 2026-09-09**: the tracker now persists on the service instance, and `OrderGuard` now calls `/portfolio/risk/status` and rejects new/increasing orders on a TIER_HALT symbol (reduce-only orders exempt). (Scenario 22)
4. **"PBO protects me from overfit strategies" — was false, now fixed.** PBO used to be computed correctly at research time and then discarded — no database column, not part of the promotion verdict. **Fixed 2026-09-09**: persisted end-to-end and now an explicit, required check in `meets_promotion_bar()`. (Scenario 19)
5. **"Correlation risk is managed" — only at the moment you place a new order.** Existing correlated positions are never revisited; the DCC-GARCH crisis-correlation signal is computed but has no consumer that acts on open positions. (Scenario 12)
6. **"A strategy that barely passes promotion is still validated" — was true, now partially fixed.** Deflated Sharpe 0.951 (bare pass) and 0.999 (strong pass, note: deflated Sharpe is a probability capped at 1.0, the original "vs 2.0" framing was off-scale) used to receive identical downstream capital. **Fixed 2026-09-09** for deflated-Sharpe margin specifically — allocation now scales with it. Still open: PBO margin has no equivalent gradient, and there is still no probationary period for freshly promoted strategies. (Scenario 34)
7. **"Rebalance requests from the capital allocator are followed" — no, they're suggestions.** `rebalance_guard.py` only checks the kill switch; the Monitor can decline a reallocation indefinitely via its hardcoded 5% gain-protect rule. (Scenario 23)
8. **"YAML strategies are validated the same way as trade_plan strategies" — was false, now fixed.** They're promoted through the same statistical gate but used to receive zero live outcome tracking forever. **Fixed 2026-09-09**: `_fetch_outcome_confidence()` now derives a real directional track record from weight + price history for YAML strategies, feeding the same allocation tilt `trade_plan` strategies already got. (Scenario 20)

---

### F. UNEXPECTED / NON-OBVIOUS GAPS (Things you likely haven't explicitly thought about)

1. **Two sources of truth for "what do I hold."** OrderGuard checks the live broker; Monitor checks its internal book, refreshed only every 90 seconds. In the 90-second window after a partial fill or a fast-moving broker-side event, these two components can act on different realities of the same portfolio. (Scenario 35, compounding Scenario 15)
2. ~~Signals never expire.~~ **Fixed 2026-09-09.** A TradePlan generated at market open with an entry zone that price never touches used to stay "valid" indefinitely — there was no `max_age`. `orchestrator.py`'s `_maybe_enter()` now rejects a plan whose `created_at` (already stamped by `trade_plan_authoring.py`, just never read before) is older than `VINU_LIVE_SIGNAL_MAX_AGE_HOURS` (default 72h). (Scenario 36)
3. **Multi-timeframe strategies can silently fight each other for the same commissions.** A 1H sweep and a 1D sweep on the same symbol occupy the same portfolio with no netting or sleeve isolation — this isn't a hypothetical, it's structurally guaranteed once you run more than one interval. (Scenario 25)
4. **The system can hold two offsetting positions and count that as "diversified."** Concentration checks look at gross weight per symbol, not at directional conflict between strategies. A long from Strategy A and a short from Strategy B on the same ticker pass every guard individually. (Scenario 3)
5. **Paper-trading validation resets on every deploy.** Because paper state isn't in a persistent volume, routine operational activity (a container restart for an unrelated bug fix) silently invalidates the 10-day paper-trading clock that money-gate.md requires before going live — nobody has to touch trading code to break this. (Scenario 28)
6. **Net P&L for short strategies is systematically overstated in every backtest and paper run**, because borrow cost, dividend obligations, and tax treatment are absent from the cost model — not approximated conservatively, simply absent. A short strategy that looks like Sharpe 1.5 on paper could be Sharpe 0.7 net, and nothing in the pipeline surfaces that gap before capital is at risk. (Scenario 26)
7. **The system has no representation of "I am not confident enough to act."** Every path — allocation, sizing, order submission — terminates in a decision. There is no code state equivalent to a human trader closing the terminal and walking away. In a genuinely unprecedented event this isn't a missing nice-to-have, it's the single biggest tail-risk gap in the system. (Scenario 30, 33)
8. **A confirmation model doesn't exist for the LLM vs the quant signal vs a human overriding.** Whichever one submits its order last wins, silently. Nobody designed this as a decision; it's an emergent property of three independent code paths that all call the same order endpoint. (Scenario 31)

---

## Bottom line

Vina is strongly built at the **mechanical, scheduled, order-time layer** (Section A) — that part is close to institutional-grade. It is weak or absent at the **adaptive, cross-component, and "what should I do when I'm uncertain" layer** (Sections C, E, F) — which is exactly the layer that separates surviving a real trading situation from not.

**2026-09-09 update:** of Section E's three highest-severity items, #1 (ShadowEvaluator) turned out to already be scheduled — a verification error on the analyst's part, corrected above — #2 (kill switch blocking exits) has now been fixed in code, and #6 (binary promotion-confidence collapse, Scenario 34) is now partially fixed: deflated-Sharpe margin genuinely tilts allocation weight. Still open within #6: PBO margin has no equivalent gradient (only the hard threshold Scenario 19 added), and there is still no probationary period for freshly promoted strategies regardless of how comfortably or barely they passed.
