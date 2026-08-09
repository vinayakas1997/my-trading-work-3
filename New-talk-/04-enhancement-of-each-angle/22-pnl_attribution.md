---
name: angle-22-pnl_attribution
status: decided
purpose: discussion and enhancement proposal for the `pnl_attribution` angle. Reference implementation lives at `../../vinu-components/vinu-initial-analysis/vinu_initial_analysis/angles/pnl_attribution/`.
---

# 22 — pnl_attribution

**Title (from spec.yaml):** PnL Attribution

## 1) Status

- Discussed: 2026-08-07
- Status: decided (design settled, not yet built)
- Reference implementation verified against real code: `compute.py` /
  `spec.yaml` at
  `vinu-components/vinu-initial-analysis/vinu_initial_analysis/angles/pnl_attribution/`,
  plus `vinu_initial_analysis/pnl_attribution_ingest.py`,
  `vinu-live/vinu_live/book/schema.py`, and `vinu-research/vinu_research/calibration.py`
  and `vinu-research/vinu_research/models.py` (traced to check for
  overlap/duplication before proposing anything).
- **Not a bars-driven forecaster** — push-fed via
  `POST /pnl-attribution/{symbol}/record` whenever a real Phase 6 trade
  position closes; `compute()` is a documented no-op for the standard
  runner path. No `model_backend` question applies; this is real trade
  outcome aggregation, not a model of any kind.
- **Real, correctly-implemented code, confirmed**: win rate / avg win % /
  avg loss %, each with a proper 95% t-distribution confidence interval,
  deduped by `position_id` so a retried feedback-loop delivery never
  double-counts a closed trade.
- **The gap, verified against the actual schema, not assumed**: every
  closed `Position` already carries an `artifact_id` — the schema's own
  comment says its whole purpose is to link back to "the Phase 4 frozen
  TradePlan artifact that authored this position... Phase 7's feedback
  loop needs this to know which forecast to score when the position
  closes." `aggregate_pnl_attribution()` ignores it completely — it only
  ever aggregates at the symbol level. The name "PnL **Attribution**"
  promises a breakdown by *what caused* the PnL; the code currently
  delivers a plain win/loss summary.
- **Checked for duplication before proposing a fix — found a related but
  distinct system, not an overlap.** `vinu-research`'s Phase 4
  `CalibrationTracker`/`CalibrationEntry` already tracks **forecast
  accuracy** (directional correctness, Brier score, magnitude error)
  keyed by the same `artifact_id`. That answers "was the forecast
  right." This angle, even enhanced, answers a different question — "did
  the trade actually make money" — which can diverge (a correct-direction
  forecast can still lose money to costs/exits; a wrong one can still
  profit). Proposing the by-`artifact_id` breakdown here does not
  duplicate Phase 4's work.
- **A real scope limit, checked directly against `TradePlan`'s schema
  (`vinu-research/vinu_research/models.py`)**: there is no structured
  field naming *which angle* (e.g. "kronos" vs "arima") produced a given
  `TradePlan`'s forecast — only a free-text `reasoning` string and
  generic `Forecast` metadata (direction/confidence/magnitude/horizon).
  So "which specific trade plan performed best" is directly answerable
  from data that already exists; "which of our 31 forecasting angles is
  actually profitable" is not a one-hop join today — closing that gap
  would need a structured origin field added to `TradePlan`/`Forecast`,
  which is out of scope for this angle's own design.
- **External validation**: P&L attribution — decomposing performance by
  its actual drivers, not just reporting an aggregate win/loss number —
  is standard, expected practice at investment banks, hedge funds, and
  asset managers, used for risk-model validation, regulatory compliance,
  and capital allocation decisions. The current code's symbol-only
  aggregation is closer to a basic performance summary than what
  "attribution" means in the field. See sources at the end.

## 2) One-line definition

PnL Attribution turns real closed trades into win-rate/avg-win/avg-loss
statistics with honest confidence intervals — and, as proposed here,
breaks those same statistics down by which specific trade plan produced
each trade, not just by symbol, so it can actually answer "attribution"
questions instead of only "how did this symbol do overall."

## 3) Decided parameters

| Parameter | Decided value | Notes |
|---|---|---|
| Data source | real closed positions, push-fed via `POST /pnl-attribution/{symbol}/record` from vinu-live's feedback loop | not bars-driven; `compute()`'s standard signature stays a documented no-op, unchanged |
| Core stats (kept as-is) | win rate, avg win %, avg loss %, total realized PnL, n_trades — each with 95% t-distribution CI (`_rate_with_ci`) | code default, correctly implemented, kept exactly as-is |
| Dedup key | `position_id` (kept as-is) | prevents double-counting on retried feedback-loop deliveries |
| **Proposed: per-`artifact_id` breakdown** | in addition to the existing symbol-level aggregate, also group closed positions by `artifact_id` and compute the same win_rate/avg_win_pct/avg_loss_pct/CI/n_trades for each group | `artifact_id` is already present on every closed position (per `vinu-live/book/schema.py`) and already flows through `closed_positions_json` unmodified — no new data collection needed, purely an aggregation-logic addition |
| Thin-sample handling | every per-`artifact_id` group still carries its own `n_observations`/CI, and groups below 2 trades report `status: insufficient_sample` (already the code's own existing behavior via `_rate_with_ci`, just applied per-group now instead of only per-symbol) | same "always show n, never silently trust a thin slice" principle used everywhere else in this project |
| Scope boundary — explicitly NOT attempted | resolving `artifact_id` further back to "which forecasting angle" | `TradePlan`/`Forecast` (vinu-research/models.py) has no structured origin-angle field today, only free-text `reasoning` — flagged as a real gap, not solved here, see §7 |
| Relationship to Phase 4 Calibration | complementary, not merged | `CalibrationTracker` (forecast correctness, Brier score) and this angle (realized dollars/percent PnL) both key on `artifact_id` and could be joined externally later (e.g. "does higher calibration score correlate with better realized PnL"), but that join is a future analysis, not part of this angle's own output |
| Backtest method | not applicable | this is live-trade aggregation, not something backtested against historical bars |
| Timeframe | 1min, 5min, 15min, 1H, 4H, 1D | **updated**: widened to the standard 6, same as every other angle — supersedes the earlier 1D-only decision (code default, kept for schema consistency; still doesn't mean much for push-fed data) |
| Time-based tagging | not applied | closed positions don't carry the intraday session/candle structure the shared tagging rule was built for; `opened_at`/`closed_at` timestamps are already stored per position if a future pass wants calendar-based slicing |

## 4) Example — what results look like

**Existing symbol-level aggregate (unchanged):**

```
symbol: AAPL
n_trades: 42
total_realized_pnl: 1830.50
win_rate: {mean: 0.55, n_observations: 42, confidence_interval: [0.40, 0.70]}
avg_win_pct: {mean: 0.031, n_observations: 23, confidence_interval: [0.021, 0.041]}
avg_loss_pct: {mean: -0.018, n_observations: 19, confidence_interval: [-0.025, -0.011]}
```

**Proposed: per-`artifact_id` breakdown, same shape, grouped:**

```
symbol: AAPL
by_artifact: {
  "artifact_a1b2c3": {
    n_trades: 18,
    win_rate: {mean: 0.67, n_observations: 18, confidence_interval: [0.45, 0.85]},
    avg_win_pct: {mean: 0.041, n_observations: 12, confidence_interval: [0.028, 0.054]},
    avg_loss_pct: {mean: -0.015, n_observations: 6, confidence_interval: [-0.024, -0.006]}
  },
  "artifact_d4e5f6": {
    n_trades: 3,
    win_rate: {mean: 0.33, n_observations: 3, confidence_interval: null, status: "insufficient_sample"},
    ...
  }
}
```

(Illustrative — the actual per-artifact split depends entirely on real
trading activity once Phase 6 positions exist; this angle has no data to
show until then.)

## 5) Storage, querying, API shape

- **Unchanged**: symbol-level aggregate row, written via
  `AngleStorage.write()` on every ingest call, `closed_positions_json`
  carried forward as the full history so re-aggregation never needs to
  re-fetch from vinu-live.
- **New**: a `by_artifact` nested dict on the same row (same pattern
  choice as the nested `predictions` dict used by lag_llama/moirai/
  Chronos/Kronos elsewhere in this project — group related sub-results
  under one row instead of exploding into many rows), computed from the
  same `combined` closed-positions list already being merged in
  `pnl_attribution_ingest.ingest_closed_positions` — no new ingest path,
  no new storage table, purely an addition to `aggregate_pnl_attribution`'s
  own output.

## 6) What we will achieve / how to use it

- The actual "attribution" this angle's name promises: which specific
  trade plan (and, once a structured origin field exists upstream,
  eventually which forecasting angle) is actually making money, not just
  an undifferentiated symbol-level win rate.
- A real foundation for the single most useful question this whole
  31-angle project should eventually answer: **which of our forecasting
  angles is actually profitable in live trading** — this angle's
  `by_artifact` breakdown is the first concrete step toward that, even
  though the final "angle name" resolution needs a separate upstream
  schema addition (see §7).
- A natural join point with Phase 4's Calibration system — external
  analysis (not built here) could compare "was this artifact's forecast
  well-calibrated" against "did this artifact's trades actually make
  money," which is a genuinely different and complementary question to
  what either system answers alone.
- Consistent with how real trading firms use PnL attribution — as a
  diagnostic for which strategies/signals deserve more capital/attention
  and which don't, not just a report card.

## 7) Deeper rationale

**Why the per-`artifact_id` breakdown and not a deeper "per-angle"
breakdown right now:** the data to do the deeper breakdown doesn't exist
yet — `TradePlan`/`Forecast` in `vinu-research/models.py` has no
structured field recording which angle's output informed a given plan,
only a free-text `reasoning` string that would need parsing/inference to
extract a source angle from, which risks getting it wrong silently. The
honest, buildable-now version is grouping by `artifact_id` (a hard,
already-present identifier) — a real, useful improvement over
symbol-only aggregation, without pretending to solve a problem the
current schema can't actually answer yet.

**Why this doesn't duplicate Phase 4's Calibration tracking:** Calibration
answers "was the forecast's direction/magnitude correct" using
`actual_return_pct` and Brier scoring — a forecast-quality question. This
angle answers "did the realized trade make/lose real money" — a trading-
outcome question. These can diverge in either direction (right call,
losing trade; wrong call, profitable trade, e.g. from a stop/tranche
exit), so having both, keyed on the same `artifact_id` for later joining,
is more informative than either alone — not redundant.

**Why external validation mattered here more than for some other
angles:** unlike a specific pretrained model (where the question is "is
this model good"), the question here was "is decomposing PnL by driver
even a real, valuable practice, or is the current symbol-level summary
already sufficient." The research confirmed it's genuinely standard,
expected practice at real trading firms — for risk validation, regulatory
compliance, and capital allocation — which is exactly what strengthens
the case for closing this gap rather than leaving the angle as a plain
performance summary.

**Open/unresolved:** the deeper "which forecasting angle is profitable"
question requires a structured origin field on `TradePlan`/`Forecast`
that doesn't exist today — flagged clearly as a real, separate follow-up
(an upstream schema change in `vinu-research`), not solved as part of
this angle. Also open: this angle has no real data to validate any of
this against until Phase 6 live trading actually produces closed
positions with populated `artifact_id`s — everything in §4 is
illustrative shape, not a measured result.

Sources checked for the external "is PnL attribution worth doing"
question:
- [P&L Attribution Analysis in Finance — KX](https://kx.com/glossary/pl-attribution-analysis-in-finance/)
- [Understanding PnL Attribution (PLA) — LinkedIn](https://www.linkedin.com/pulse/understanding-pnl-attribution-pla-prashant-kumar)
- [Optimal Linear Signal: Unsupervised ML Framework to Optimize PnL (arXiv:2401.05337)](https://arxiv.org/html/2401.05337)
