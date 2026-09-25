# Track 1: how the must-condition recorder actually works today

Everything in this file is real, checked directly against the current
code (not paraphrased from an earlier design conversation) as of
2026-09-25. Where a number or field name is stated, it was read from the
actual source, not assumed.

## What it does, end to end

1. `vinu-initial-analysis`'s angle #29, `signal_evidence`
   (`vinu_initial_analysis/angles/signal_evidence/compute.py`), runs as
   part of the normal angle pipeline — the same screener-discovers-a-
   ticker → download-bars-for-a-date-range → run-every-angle flow every
   other angle goes through. Nothing new to trigger it; it's automatic
   for every ticker.
2. For the bars it's given (whatever `[from_ts, to_ts]` window that run
   covers), it walks the whole series looking for every historical
   moment SMA(5) crosses above SMA(50) — the one must-condition currently
   wired in (`MUST_CONDITION_NAME = "sma5_cross_sma50"`).
3. For each crossing found, **if there's enough forward history in the
   given bars to measure a full outcome window** (see "the horizon"
   below) — two things happen:
   - A **52-indicator snapshot** is computed, strictly point-in-time
     (using only bars up to and including the trigger bar — never
     anything from after it).
   - An **outcome path** is computed using the bars forward of the
     trigger (this is only valid because backtesting already has that
     "future" data sitting in the same DataFrame).
4. Both get POSTed to `vinu-research`'s `SignalEvidenceStore` over HTTP,
   idempotently (re-running over an overlapping window doesn't create
   duplicate rows or errors — a `409` on an already-recorded trigger is
   treated as success).

If a crossing is found but there aren't enough forward bars yet to
measure its outcome, it's skipped honestly (not recorded as a failure) —
a later run whose window extends further forward will pick it up.

## The 52 indicators, exactly

All computed via `vinu_tools`' real indicator library (never hand-rolled
— see `06-mistake-duplicated-indicator-logic.md` for why that mattered),
one vectorized pass over the whole bar series, then read out by position
per trigger:

- `adx`, `rsi`
- `sma_5`, `sma_10`, `sma_20`, `sma_50`, `sma_100`, `sma_200`
- `ema_5`, `ema_10`, `ema_20`, `ema_50`, `ema_100`, `ema_200`
- `dist_from_sma_5`...`dist_from_sma_200` (6), `dist_from_ema_5`...`dist_from_ema_200` (6)
- `roc_5`, `roc_10`, `roc_20`
- `atr_14`
- `stoch_k_14`, `stoch_d_14`
- `bollinger_band_width`, `bollinger_percent_b`
- `macd_line`, `macd_signal`, `macd_histogram`
- `aroon_up`, `aroon_down`
- `cci_20`
- `williams_r_14`
- `supertrend`
- `high_low_spread`, `open_close_return`
- `momentum_10`
- `ichimoku_tenkan`, `ichimoku_kijun`, `ichimoku_senkou_a`, `ichimoku_senkou_b`
- `parabolic_sar`
- `obv`, `volume_vs_avg20`
- `vwap_dist` (session-sliced by UTC calendar date — VWAP resets each
  session the way it should, not accumulated forever)
- `cmf_20`
- `mfi_14`
- `accumulation_distribution_line`

Longer-lookback ones (e.g. `sma_200`) simply come back absent for
triggers too early in a ticker's history to have 200 bars yet — not an
error, just "not available yet."

**Deliberately NOT included**: the other 28 angles' own outputs. Using
their stored "latest" result for a historical trigger would leak
look-ahead bias (see `../01-planning.md` Decision 10) — "latest" means
whenever that angle last happened to run, not the historical trigger
moment. This is fixable (Decision 10 describes `read_as_of()`, a
point-in-time-safe read), but not built yet.

## The outcome path

Three numbers, computed from the bars forward of the trigger over a
fixed window:
- `max_favorable_excursion` — best price move reached within the window
- `max_adverse_excursion` — worst price move reached within the window
- `return_at_horizon` — the return at the end of the fixed window

## The knobs (env-overridable, `VINU_SIGNAL_EVIDENCE_<SETTING>`)

| Setting | Default | Meaning |
|---|---|---|
| `min_observations` | 70 | Minimum bars needed before this angle will even attempt anything |
| `sma_fast` / `sma_slow` | 5 / 50 | The must-condition's two moving averages |
| `adx_period` / `rsi_period` | 14 / 14 | |
| `volume_avg_period` | 20 | |
| `forward_horizon_bars` | 20 | How many bars forward the outcome path is measured over — a guessed constant, not yet derived from real data (see `../01-planning.md` Decision 12's own note on this) |
| `cci_period` / `williams_r_period` / `cmf_period` / `momentum_period` / `mfi_period` | 20 / 14 / 20 / 10 / 14 | |

`VINU_RESEARCH_API_URL` (default `http://localhost:8087`) — where the
angle POSTs to.

## The real storage schema (`vinu-research`)

Two tables (`vinu_research/storage/signal_evidence_store.py`):
- `signal_triggers` — one row per trigger: `trigger_id`, `symbol`,
  `trigger_time`, `must_condition` (JSON list), `granularity`,
  `policy_version`, the three outcome fields (nullable until filled),
  `outcome_recorded_at`.
- `signal_evidence_indicators` — one row per `(trigger_id,
  indicator_name)` pair, `indicator_data` a JSON blob. This is how "one
  JSON column per indicator" (Decision 3) is actually realized in SQL —
  a normalized child table, not 52 literal SQL columns.

## How to actually query it today — three ways

**1. Raw HTTP** (`vinu-research`, base path `/research`):
- `POST /signal-evidence/trigger` — record a trigger (used internally by
  the angle; you'd only call this by hand for testing).
- `POST /signal-evidence/{trigger_id}/outcome` — fill in the outcome.
- `GET /signal-evidence/{trigger_id}` — one trigger's full row +
  indicators.
- `GET /signal-evidence?symbol=AAPL&limit=50` — a symbol's triggers,
  metadata only (no indicators, for browsing).

**2. An LLM tool call** — `get_signal_evidence`
(`vinu-agent/vinu_agent/tools/signal_evidence_tool.py`), read-only,
currently wired into the `theory_reviewer` agent (`thesis_intake` team)
only. Takes `symbol` (optional), `trigger_id` (optional — fetches one
event's full snapshot instead of the summary list), `limit` (optional,
default 50). Tries an in-process store read first
(`get_signal_evidence_store()` in
`vinu_agent/broker/research_link.py`), falls back to the HTTP routes
above on any failure (missing package, service unreachable, etc). The
summary-list response is always honest raw counts — `{status, symbol,
count, outcomes_recorded, triggers}` — never a computed win rate or
statistic, because Phase 3 (the analysis layer) doesn't exist yet.

**3. The per-ticker coverage view** — `GET /analysis/coverage/{ticker}`
in `vinu-initial-analysis` tells you whether `signal_evidence` has even
run for a given ticker yet (it's just angle #29 in that view, same as
every other angle — `pending` / `not_required` / a real status).

## What doesn't exist yet (as of this file)

- **No real data has actually accumulated.** Every number above is
  verified against the code and tests, but as of the last check, no
  `.db` file for `SignalEvidenceStore` existed anywhere under
  `vinu-components/data/` — this has only ever been run against
  synthetic test fixtures, never a real ticker's real history.
- **Phase 3 (the analysis/bucketing layer)** — turning these raw rows
  into actual win-rate/expectancy-by-bucket statistics — is not built.
  See `../01-planning.md`'s pending decision log.
- **The LIVE detector** — something in `vinu-live` generating a NEW
  trigger the instant it happens during real trading, not just this
  angle's periodic historical backfill sweep — does not exist.
