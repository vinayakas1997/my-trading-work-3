# How to Make Vina Live — Staged Build Plan

## What this file is (and isn't)

`seceniors.md` (one folder up, `the-full-comprehensive-analysis/seceniors.md`)
documents **what's broken**: 36 real-world trading scenarios stress-tested against the
actual `vinu-components` code. As of this file's latest update, 30 are still open, 6
were found already fixed during verification, and 2 more (the CVaR/vol-target flags,
and the global kill switch's exits-during-halt gap) were fixed live in this session —
see `CHANGES-2026-09-09.md` in this same folder for the exact diff-level record of
what was changed, why, and how to verify it.

This file is different. It is **not** sourced from any pre-existing document — it's my
own engineering synthesis, built by rereading the actual code paths (the same files
greped through while verifying `seceniors.md`) and judging which fixes are small
copy-an-existing-pattern jobs versus which need new data sources or architecture.
Treat the *list of 31 gaps* as verified against code; treat the *staging, effort
estimates, and specific fix suggestions below* as engineering judgment formed during
this session, not something written down anywhere beforehand. Confirm each Stage 1/2
estimate against the real diff size before committing to a timeline.

The goal: stop stopping at "no, this isn't handled" and instead give a concrete,
staged path to "yes."

---

## Stage 0 — Already done before this session, don't touch (6 of 36)

Verified fixed in code (see `seceniors.md`'s Verification Audit for evidence and
ratings):

- **#4** Time-stop (`max_hold_days`) + default 2×ATR trailing stop, unconditional
- **#7** Revenge-trade cooldown — 2 losses locks a symbol's entries for 24h, exits exempt
- **#18** ShadowEvaluator scheduling — `entrypoint.sh` runs `vinu-live shadow-worker &`
  as a real background daemon. (This was wrongly marked open earlier in this same
  analysis — a verification error on the analyst's part, checking `scheduler.py`
  instead of `entrypoint.sh`. Corrected in `seceniors.md`.)
- **#27** Idempotency keys — `client_order_id` computed on every order (though see
  Stage 1 below: the value was computed correctly but dropped before reaching the
  broker until this session's fix)
- **#28** Paper-trading state persistence — bind-mounted, not tmpfs

---

## Stage 1 — DONE (this session, 2026-09-09)

Was "This week, near-zero engineering." All three planned items are now implemented in
code, plus one bug found along the way. Full diff-level record: `CHANGES-2026-09-09.md`
in this folder.

| Fix | Status | Where |
|---|---|---|
| Flip `VINU_RISK_CVAR_ENABLED=true` and `VINU_RISK_VOL_TARGET_ENABLED=true` | ✅ Done | `.env` |
| Give the **global** kill switch a `reduce_only` exemption, same policy vinu-live's local breaker already used | ✅ Done | `order_guard.py`, `trade_tool.py`, `routes_broker.py`, `orchestrator.py` |
| ~~Schedule ShadowEvaluator~~ | Not needed — already scheduled (moved to Stage 0, was a verification error) | — |
| **Bonus fix found while wiring #21**: `client_order_id` (the #27 idempotency key) was computed by vinu-live but silently dropped at the HTTP boundary — `OrderRequest` never declared the field, so it never reached Alpaca and the dedup never actually ran | ✅ Done | `base.py`, `alpaca.py`, `routes_broker.py`, `trade_tool.py` |

**After Stage 1:** both remaining DANGEROUSLY MIS-HANDLED scenarios that needed code
(21) are closed; #18 turned out not to have needed anything. Only #34 (binary
promotion-confidence collapse) remains from the original three highest-severity items,
and it's a Stage 2 item, not a Stage 1 one.

---

## Stage 2 — 1–2 weeks, wiring fixes (no new architecture)

Every fix here follows a pattern that already exists somewhere else in the codebase —
copy it to the place that's missing it, don't invent anything new.

**#22 (risk budget enforcement) is done** — see `CHANGES-2026-09-09.md`. `OrderGuard`
now calls `GET /portfolio/risk/status` and rejects new/increasing orders on a
TIER_HALT symbol (reduce-only orders exempt). A separate, real bug was found and
fixed along the way: `compute_risk_status()` built a fresh `DailyPositionTracker`
every call, so daily P&L never actually accumulated — moved onto the service
instance so it now persists for the trading day.

**#19 (PBO persistence) is done** — see `CHANGES-2026-09-09.md`. `pbo` columns added
to both `research_runs` and `artifacts`, written at the same point
`holdout_passed`/`stress_test_passed` already are, and `promotion.meets_promotion_bar()`
now rejects on PBO above threshold or PBO required-but-never-computed. Both read-path
gaps the original analysis called out (`GET /research/runs/{id}`, the artifact-list
endpoint) also fixed — neither returned `pbo` even before persistence existed.

**#24 (forecast confidence → sizing) is done** — see `CHANGES-2026-09-09.md`.
`position_sizing.py`'s `compute_position_size()` gained a `forecast_confidence`
multiplier (same pattern as `cvar_95`/`current_vol`), and — the fix that actually
matters for a real TradePlan — `orchestrator.py`'s `_maybe_enter()`, the real live
entry-sizing point, now scales `risk_bands.max_position_size_pct` by
`forecast.confidence` before computing order qty. Floored at 0.5 so a real forecast
dampens size, never zeroes it.

**#20 (YAML strategy outcome tracking) is done** — see `CHANGES-2026-09-09.md`. Ended
up not touching `MetaStorage` — YAML strategies have no discrete open/closed
positions, so there was nothing to write to a P&L column the way `FeedbackLoopWorker`
does for `trade_plan` artifacts. Instead `_fetch_outcome_confidence()` now computes a
real directional track record on read, from the weight history + price history
`vinu-portfolio` already fetches elsewhere — same three-state contract
(`not_tracked`/`insufficient_data`/a real accuracy), feeding the same allocation
multiplier `trade_plan` artifacts already used.

**#36 (signal TTL) is done** — see `CHANGES-2026-09-09.md`. Turned out
`TradePlan.created_at` already existed and was already being stamped at generation
time in the real authoring path (`trade_plan_authoring.py`); nothing downstream ever
read it. `orchestrator.py`'s `_maybe_enter()` now rejects a plan older than
`VINU_LIVE_SIGNAL_MAX_AGE_HOURS` (default 72h). This closes half of #9 as a side
effect (the "stale signal stays actionable forever" half) — the other half
(real-time hesitation-cost measurement, proactive aging alerts) is untouched and
#9 remains listed as open/partial in `seceniors.md`.

**#8 (portfolio-level daily order cap) is done, partially** — see
`CHANGES-2026-09-09.md`. `mandate.max_daily_orders_portfolio` +
`DailyLimitStore.count_today_total()` close the specific "10/symbol × 20 symbols =
200/day" gap the scenario opened with (ships disabled — the right ceiling depends on
deployment). Turnover-as-a-percentage and transaction-cost-aware sizing, the
scenario's other two gaps, are untouched — Scenario 8 stays marked PARTIALLY HANDLED.

**#34 (confidence-gradient sizing) is done, partially** — see
`CHANGES-2026-09-09.md`. `vinu-portfolio`'s `compute_daily_allocation()` gained a
third bounded tilt, `_confidence_gradient_multiplier()`, mapping deflated-Sharpe
margin above the promotion threshold into the same `±0.3` band `regime_multiplier`/
`outcome_multiplier` already use — a bare pass now gets less capital than a strong
pass. Note the scenario's own "0.95 vs 2.0" framing was off-scale: deflated Sharpe is
a probability capped at 1.0, not an unbounded ratio, so the real range is
`[threshold, 1.0]`. Still open: PBO margin has no equivalent gradient (only
Scenario 19's hard threshold), and there's still no probationary period for newly
promoted strategies — Scenario 34 stays marked PARTIALLY HANDLED (downgraded from
DANGEROUSLY MIS-HANDLED), not resolved.

**Stage 2 is complete** — all 7 originally-listed items addressed (5 fully resolved,
2 — #8 and #34 — partially, both correctly left open/partial in `seceniors.md`
rather than marked resolved).

**After Stage 2:** 12 of 36 scenarios resolved, plus 2 more (#8, #34) meaningfully
improved but still open. Everything rated CRITICAL or DANGEROUSLY MIS-HANDLED that
isn't fundamentally a missing-data problem has now been addressed at least in part.

---

## Stage 3 — 2–4 weeks, real new logic inside existing components

Genuinely new logic, but still contained within components that already exist —
no new services, no new data feeds.

| # | Fix | What it takes |
|---|---|---|
| 12 | Runtime correlation monitor | Monitor cycle calls the existing `shock_correlation.py` DCC-GARCH against *open* positions (today it only runs at order time / daily allocation), triggers a reduce action past a threshold |
| 3 / 5 | Conflicting-signal detection | Before funding/entering, check other ACTIVE artifacts' current signal on the same symbol; net or block on direct opposition |
| 15 | Partial fill handling | `filled_qty` vs intended qty is already flowing through `debrief.py` — add residue cancellation after a timeout and adjust the book to the actual filled size |
| 16 | Data freshness guard | Timestamp check on the latest price before Monitor/OrderGuard act; pause entries (not exits) on stale data, same policy shape as HALT entries-only |
| 23 | Rebalance force override | A "critical" flag on `rebalance_request` that bypasses the hardcoded 5% gain-protect for genuinely urgent reallocations |

---

## Stage 4 — Larger effort, needs new data sources or infrastructure

These are real gaps, but they need a new data feed, a new service, or an
architecture change — they are not what's standing between the system and live
capital in the next month.

| # | Gap | Why it's Stage 4 |
|---|-----|-------------------|
| 2 | Event risk (earnings, FDA, corporate actions, borrow rate) | Needs a calendar/events data source that doesn't exist yet |
| 13 | Liquidity / spread gate | Needs real-time spread/depth data, not just price |
| 14 | Broker fallback + outage pause | Needs a second broker integration and failover logic |
| 25 | 1D/1H timeframe sleeves | Portfolio architecture change — separate capital pools per timeframe |
| 26 | Borrow / dividend / tax modeling | New cost model, needs borrow-rate and dividend-calendar data |
| 29 | Secrets vault | Infra change (AWS Secrets Manager / Vault integration) |
| 33 | Out-of-distribution detector + emergency flatten | New detector, new "flatten everything" action path |
| 32 | Broader learning loop (sizing, regime, correlation) | Needs a training/retraining pipeline, not a single fix |
| 35 | Sub-90-second book/broker reconciliation | Event-driven reconciliation instead of periodic polling — a real architecture change |

---

## Stage 5 — The judgment layer (pair with Stage 2/3 enforcement, never standalone)

This is where "context engineer a strong prompt" is actually the right tool — but
only paired with a coded consumer of the LLM's output, never as a standalone
safeguard. LLM instruction-following is probabilistic; a coded threshold on a score
the LLM emits is not.

| # | Gap | Pattern |
|---|-----|---------|
| 1 | FOMO / chasing entries | LLM scores "chase risk" at entry time (it's already being invoked to write the trade plan); a coded size dampener acts on the score |
| 10 / 11 | Stop quality / thesis-vs-market-noise | LLM classifies noise-vs-break at the invalidation trigger point; coded confidence threshold decides hold vs exit |
| 30 | "I don't know" / uncertainty | LLM emits an explicit confidence/uncertainty score; coded rule scales size toward zero below a threshold |
| 31 | Model disagreement (quant vs LLM vs human) | Code aggregates all three signals; a weighted/majority arbitration rule decides, not "whichever order lands last" |

---

## The path to "yes"

Stage 1 is done — it closed every currently-dangerous blind spot that needed code (one
of the original three turned out to need nothing). Stage 2 is done — all 7 items
addressed (#22, #19, #24, #20, #36, #8, #34), 5 fully resolved and 2 (#8, #34)
meaningfully improved but correctly left open/partial rather than marked resolved.
Stages 3–4 are the real timeline cost — genuine new logic and new data/infra. Stage 5
is where prompt/context engineering earns its place, but only once Stages 1–3 give it
something concrete to enforce against.

Net picture so far: **12 of 36 scenarios resolved**, plus 2 more meaningfully
improved (see `seceniors.md`'s updated tally).

Cross-reference: full scenario-by-scenario evidence and verified status for every item
above lives in `seceniors.md` one folder up. The exact code changes made in this
session are recorded in `CHANGES-2026-09-09.md` in this same folder.
