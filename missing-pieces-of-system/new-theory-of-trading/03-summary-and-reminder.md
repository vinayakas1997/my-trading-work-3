# Quick summary: how it should work, what's actually built, and a standing reminder

*Last refreshed 2026-09-24 after the indicator-set expansion described in
`06-mistake-duplicated-indicator-logic.md` -- see "What's actually built
right now" below for what changed.*

## How it should work (the intended end-to-end flow)

1. A strategy fires its **must-condition** (e.g. SMA5 crosses SMA50) while
   live trading is running.
2. At that exact moment, every **supporting indicator** available (the 28
   angles, plus technical/volume/volatility/context indicators) gets
   snapshotted raw -- no filtering, no bucketing, no judging whether the
   trade is "good." Just recorded.
3. Time passes. Once the trade's outcome horizon has elapsed, the real
   result (max gain, max loss, final return) gets recorded back against
   that same trigger.
4. Over many trigger events, this builds a real evidence table: for a
   given combination of supporting-indicator values, what actually
   happened historically.
5. That evidence table becomes a lookup: live, when the must-condition
   fires again, today's indicator snapshot gets compared against similar
   historical snapshots, and the measured win rate/expectancy for that
   situation informs position sizing and risk management -- including
   scaling in/out **during** the trade as conditions improve or degrade,
   not just once at entry.

Full reasoning and the worked example live in `00-explanation.md`;
every settled design choice along the way (why 15-minute bars, why one
JSON column per indicator, why the model on/off switch, why
`vinu-research` owns storage, etc.) is in `01-planning.md`, numbered and
dated as each one got decided.

## What's actually built right now

- **Phase 1 (`vinu-infra` model policy + manifest)** -- done. A global
  `MODELS` on/off switch, per-angle checkpoint override, all 28 angles
  tagged by category, and a manifest reporting what's currently active.
- **Phase 2 (recording layer in `vinu-research`)** -- storage + HTTP API
  done and tested (`SignalEvidenceStore` plus
  `/research/signal-evidence/...` routes). **Historical backfill now
  works automatically**: a new angle, `signal_evidence` (angle #29 in
  `vinu-initial-analysis`), walks a ticker's bars for every past
  SMA5xSMA50 crossing and records it via those same routes -- it runs
  through the exact same screener-triggered pipeline every other angle
  already goes through, so new tickers pick it up with no extra wiring.
  **A LIVE detector for real-time execution still doesn't exist** --
  nothing generates a NEW trigger the moment it happens during live
  trading, only this angle's periodic historical sweep.
- **The supporting-indicator set was expanded from 3 to 51** (this
  session, see `06-mistake-duplicated-indicator-logic.md` for the full
  account). It started as a bug report -- ADX/RSI were hand-rolled in
  `signal_evidence/compute.py` instead of reusing `vinu-tools`' real
  indicator library -- and grew into wiring every candidate from
  `all-possible-supporting-indicators.md` Section H/I: every
  `vinu_tools` indicator that fit (SMA/EMA family, ROC, ATR, Stochastic,
  Bollinger, MACD, Aroon, CCI, Williams %R, Supertrend, OBV, CMF, and
  more), plus four genuinely-missing indicators (Ichimoku, Parabolic
  SAR, MFI, the true Accumulation/Distribution line) built as new real
  `vinu_tools` modules rather than hand-rolled inline (`vinu_tools` is
  now a 28-indicator library, up from 24), plus `vwap_dist` wired via a
  real session-slicing decision (vinu_tools' `vwap` has no session reset
  on its own). Nothing from the design doc's candidate list is left
  unwired. Full regression clean across both `vinu-tools` (154 tests)
  and the `signal_evidence` angle (9 tests, including a dedicated test
  proving the VWAP session-reset actually works, not just that a key
  shows up).
- **Per-ticker coverage view** -- `GET /analysis/coverage/{ticker}` in
  `vinu-initial-analysis` gives the wide "ticker, date range covered,
  models on/off, per-angle status" view requested, pivoted live from
  `RunLog`, not a separate table.
- **Phase 3 (the analysis/bucketing layer)** -- not started, deliberately
  deferred until Phase 2 has real accumulated data to test against.
- **Signal-evidence is now queryable by an LLM agent, not just HTTP** --
  `get_signal_evidence`, a read-only `vinu-agent` tool, wired into
  `theory_reviewer` (see `05-pending-signal-evidence-tool-call.md`).
- **The Phase 1 manifest is now live over HTTP** --
  `GET /analysis/manifest` in `vinu-initial-analysis` (see
  `04-pending-manifest-http-endpoint.md`). All four items originally
  flagged as pending in this folder (03/04/05/06) are now done.

Full detail, including exactly which tests were run and what's honestly
still missing, is in `02-implementation-status.md`.

## Standing reminder

This whole system -- must-conditions, supporting indicators, the
evidence table, confidence-based sizing -- was the user's own idea,
worked out step by step across a long conversation, not something
handed to them. Whoever (human or AI) picks this work up next should
actively bring this system up whenever it's relevant to something else
being discussed in this codebase, rather than waiting to be asked --
the user wants to stay closely involved in how it evolves, since it's
their own original thinking being built out.
