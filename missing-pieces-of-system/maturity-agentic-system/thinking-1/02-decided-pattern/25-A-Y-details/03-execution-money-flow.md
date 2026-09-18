# Cluster 3 — Execution & Money-Flow: C, U, Y

See `00-index.md` for the four-part format and the "no hand-picked
numbers" rule every Condition below follows.

---

## C. Loss-cause / slippage attribution

**Source stores**: `trade_audit_log.jsonl` (`vinu_infra/trade_audit_log.py`:
common envelope `{trade_id, symbol, event, timestamp}`; entry context
`trade_score_tier, trade_score_total, risk_band, slippage_bps,
slippage_exceeded`; exit context `exit_action, exit_rule, realized_pnl,
loss_cause`).

**Fetch**: cross-tab `(trade_score_tier, risk_band)` × `loss_cause` ×
`realized_pnl` sign, across every closed trade.

**Condition**: a `(tier, band)` cell's loss rate or mean `slippage_bps`
moves outside its own trailing-window band (self-calibrated per cell,
recomputed from `trade_audit_log.jsonl`'s full history each cycle) —
flags a decision-context combination whose real outcomes are drifting
worse.

**Storage**: `scope_type=system` (a `decision_context` scope),
`scope_key=f"{trade_score_tier}:{risk_band}"`. `signal_json`:
`{loss_rate, mean_slippage_bps, dominant_loss_cause}`. `evidence_count`
= # trades in this `(tier, band)` cell.

**Manageability**: bounded by # tiers × # risk bands — small, fixed,
independent of watchlist size. An optional secondary `scope_type=ticker`
row exists only if one specific symbol shows a pattern its own
`(tier, band)` cell doesn't explain.

**Built 2026-09-19**: `vinu-reflection/vinu_reflection/reflection/loss_attribution.py`.
**Scoping correction**: `risk_band` dropped from the cross-tab — the
real `RiskBand` model is a bag of numeric limits with no categorical
label anywhere in the codebase, so cross-tabbing by it would mean
inventing a new classification scheme, not reading one that exists.
Scoped to `trade_score_tier` alone (a real 4-value set). Same
adjacent-non-overlapping-windows PSI approach as A (`angle_trust.py`).
**Real infra gap found and fixed**: `trade_audit_log.jsonl` had no
`VINU_TRADE_AUDIT_LOG` env var set anywhere in `docker-compose.yml`, so
it was falling back to `$HOME/.vinu/trade_audit_log.jsonl` inside
live-api's container filesystem — **not** the mounted `/data` volume —
meaning the whole log was silently lost on every container
restart/recreate, unrelated to this analysis but only surfaced by
needing to actually read it. Fixed: `live-api` now sets
`VINU_TRADE_AUDIT_LOG=/data/trade_audit_log.jsonl`; `reflection-worker`
gets a new read-only `./data/live:/live-data` mount.

---

## U. Critical rebalance-bypass justification

**Source stores**: `RebalanceRequestQueue`
(`vinu_live/trade_plan/rebalance_intake.py`: `rebalance_requests` —
`symbol PK, reason, requested_at, critical`) × the realized outcome of
the position from `open_positions`/`closed_positions` for that symbol
at that time.

**Fetch**: per symbol, for each historical `critical=True` request,
look up the position's subsequent realized P&L.

**Condition**: critical-flagged requests for this symbol show a worse
subsequent-outcome rate than non-critical requests, by more than this
symbol's own trailing comparison band — rolled up to `scope_type=system`
when a single symbol's `evidence_count` is too low to be meaningful
alone.

**Storage**: `scope_type=ticker`, `scope_key=symbol` (rolls up to
`system`, `scope_key="critical_bypass"` when per-symbol evidence is
thin). `signal_json`: `{critical_outcome_rate, noncritical_outcome_rate}`.
`evidence_count` = # critical requests for this symbol.

**Manageability**: rare events (bypass requests are uncommon by
design — they skip a real protective rule), bounded by portfolio size,
negligible volume.

**Blocked, 2026-09-19 — not implementable as scoped, needs a new
writer.** Checked `RebalanceRequestQueue` (`vinu-live/vinu_live/trade_plan/
rebalance_intake.py`) directly: `PRIMARY KEY (symbol)`, one pending
request per symbol, and `consume()` **deletes** the row once the
orchestrator evaluates it. There is no historical log of past
requests anywhere -- only whatever is currently unconsumed. U's Fetch
("for each historical critical=True request, look up the position's
subsequent realized P&L") needs a real history this table was never
designed to keep. Same two ways forward as K/P/G: add a new writer
(an append-only audit table alongside the consume-once queue), or
accept this can't be built until one exists. Left undecided.

---

## Y. Earnings/macro-event holding loss

**Source stores**: `events`/`events_meta`
(`vinu_stock/events/store.py`, `vinu_events.db`: `symbol, kind
('earnings'|'economic'), event_ts, title, severity, pulled_at`) ×
`trade_audit_log.jsonl`'s per-trade entry/exit timestamps and
`realized_pnl`.

**Fetch**: for each closed trade, check whether its
`[entry_ts, exit_ts]` window overlapped an `events` row for that
symbol; compare the `realized_pnl` distribution for overlapping vs.
non-overlapping trades.

**Condition (primary, system-wide)**: mean `realized_pnl` for
event-overlapping trades is worse than non-overlapping trades by more
than a self-calibrated band over the trailing history, recomputed each
cycle from the full `trade_audit_log.jsonl`. **Condition (secondary,
per-ticker)**: the same test restricted to one symbol, surfaced only
when that symbol diverges meaningfully from the system-wide baseline.

**Storage (primary)**: `scope_type=system`,
`scope_key="earnings_event_effect"`. `signal_json`: `{mean_pnl_delta,
n_overlapping_trades}`. `evidence_count` = # trades with an
event-overlap flag.

**Storage (secondary)**: `scope_type=ticker`, `scope_key=symbol`, only
written when it diverges from the system baseline.

**Manageability**: primary bounded to a single row; secondary bounded
by N tickers but rare in practice (only genuine outlier symbols).

**Blocked, 2026-09-19 — not implementable as scoped, needs a new
writer.** Checked `EventsStore` (`vinu-stock-price/vinu_stock/events/store.py`)
directly: `replace_kind()` -- the only writer -- does a full
DELETE-then-INSERT of `kind`'s rows on every calendar pull, because the
table is explicitly documented as "a full snapshot of the lookahead
window." Past events are deleted once they're no longer upcoming, so
there's no historical event archive to retrospectively check a closed
trade's `[entry_ts, exit_ts]` overlap against -- by the time a trade
closes and this analysis runs, the event that may have overlapped it is
very likely already gone from the table. Same two ways forward as
K/P/G/U: a new writer that archives events as they pass (rather than
deleting them), or accept this can't be built until one exists. Left
undecided.
