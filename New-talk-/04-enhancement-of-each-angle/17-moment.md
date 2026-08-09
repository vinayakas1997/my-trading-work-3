---
name: angle-17-moment
status: decided
purpose: discussion and enhancement proposal for the `moment` angle. Reference implementation lives at `../../vinu-components/vinu-initial-analysis/vinu_initial_analysis/angles/moment/`.
---

# 17 — moment

**Title (from spec.yaml):** MOMENT Multi-Task Time-Series Foundation Model (fallback proxy)

## 1) Status

- Discussed: 2026-08-07
- Status: decided (design settled, not yet built)
- Reference implementation verified against real code: `compute.py` /
  `spec.yaml` at
  `vinu-components/vinu-initial-analysis/vinu_initial_analysis/angles/moment/`
- **Currently always `fallback_proxy` — confirmed real**, same as
  lag_llama/moirai: `compute.py` hardcodes
  `"model_backend": "fallback_proxy"` on every successful row.
- **Blocker is a real, confirmed build failure, not a network/missing-
  package issue.** `pip install momentfm` was actually attempted and
  failed: `AttributeError: module 'pkgutil' has no attribute
  'ImpImporter'` — one of `momentfm`'s transitive build dependencies uses
  a `pkgutil` API removed in Python 3.12 (the shared env's version). This
  is a different *class* of blocker than lag_llama/moirai's torch-
  downgrade risk — it doesn't threaten the 5 already-wired real loaders,
  it's purely a Python-version incompatibility.
- **Decision: real-weights wiring will not be pursued — not "on hold,"
  not "low-priority future work," a settled no.** This isn't primarily
  about the build blocker (which is arguably the most fixable of the
  three fallback-proxy angles — an isolated older-Python venv could
  plausibly resolve it without touching the shared environment at all).
  It's because the real model itself doesn't clear the bar once actually
  researched — see §7 for the full case. In short: MOMENT's own
  literature states forecasting is its weakest capability, it's
  explicitly "undertrained" relative to TimesFM/MOIRAI/Chronos, and its
  masked-encoder architecture family is generally outperformed by the
  decoder-based models (Chronos, TimesFM, Kronos) this project already
  has genuinely wired and working. This angle only implements MOMENT's
  forecasting task — its weakest task — so there's little realistic
  upside even if the build issue were fixed.
- Shared/common piece this depends on: [common-rule-of-time-slicing-tags.md](common-rule-of-time-slicing-tags.md),
  applied unchanged.

## 2) One-line definition

MOMENT, as this codebase actually runs it today, is not the real
pretrained AI model — it's a simple statistical formula that takes a
stock's average recent return and projects it forward as a straight
compounding drift, with a rough range attached, standing in for a real
model that — after being checked against its own published track record —
turned out not to be worth chasing down for this particular job anyway.

## 3) Decided parameters

| Parameter | Decided value | Notes |
|---|---|---|
| Model backend | always `fallback_proxy` | confirmed from code; every stored row carries this label plus `fallback_reason` and `task_note` |
| Underlying fallback method | seasonal-naive-adjusted drift: point forecast = last close × (1 + recent avg return)^step, spread from residual std × √step | code's real method — a geometric random walk with drift, simpler than moirai's AR(3) or lag_llama's AR(5); no lag-coefficient fitting at all |
| Min observations (N) | 100 candles | raised from the code's current floor (`MIN_OBSERVATIONS = 20`), same consistency move as every other angle |
| Forecast horizon | 5 steps ahead | code's `HORIZON = 5`, same as lag_llama/moirai/Chronos/Kronos |
| Uncertainty band | point forecast + p10/p90 (single 80% interval) | code's real, exposed output — same shape as moirai's, narrower than lag_llama's 5-level set |
| Primary evaluation metric | CI-coverage: actual close falls inside [p10, p90] | same principle as moirai/lag_llama |
| Secondary evaluation metric | pinball loss on the 2 available quantile levels (0.10, 0.90), per horizon step | same reasoning as moirai — pinball loss works for any number of real quantile levels |
| Tertiary evaluation metric | RMSE and MAE between point forecast and actual close, per horizon step | same "how close in dollars" addition as every other point/quantile-output angle |
| Diagnostic fields stored | point forecast, p10, p90, actual close, hit (in-band), pinball loss, close_sq_error, close_abs_error — per horizon step | same as moirai/lag_llama |
| Backtest method | walk-forward (rolling refit + forecast + check, slide forward) | same method as all other angles |
| Storage shape | one row per walk-forward evaluation, nested `predictions` dict keyed by horizon step (1-5) | same nested-dict pattern as moirai/lag_llama/Chronos/Kronos |
| Task scope | forecasting only | matches the code exactly — MOMENT's embeddings/classification/anomaly-detection/imputation tasks are not implemented in this angle and are out of scope here |
| Timeframes | 1min, 5min, 15min, 1hr, 4hr, 1day | widened from the spec's current 1D-only, same as every other angle |
| Date range | 2022-01-01 → 2026-Q2 | same as other angles |
| Data source | Alpaca | same as other angles |
| Baseline comparison | naive random-walk (forecast = last close), same backtest | same rationale as other angles |
| Symbol scope | parameterized — specific ticker or all tracked tickers | same as other angles |
| Time-based tagging | session / day-of-week / week / month / quarter | shared rule, see [common-rule-of-time-slicing-tags.md](common-rule-of-time-slicing-tags.md) |
| Compute cost | trivial, not a concern | closed-form drift/std computation, cheapest of all three fallback-proxy angles |
| Real-weights path | **decided against — will not be implemented** | not a build-fix backlog item; a considered no, see §7 |

## 4) Example — what one result looks like

**One walk-forward evaluation (one row, nested predictions):**

```
symbol: AAPL
timeframe: 1D
candle_ts: 2024-05-15T13:30:00Z
session: ny
subsession: markethours
day_of_week: Wednesday
week_of_month: 3
month: May
quarter: Q2
model_backend: fallback_proxy
fallback_reason: "momentfm failed to build in this Python 3.12 env
  (pkgutil.ImpImporter removed, confirmed via real install attempt).
  Real-weights wiring will not be pursued regardless — MOMENT's own
  literature reports forecasting as its weakest task, and its
  masked-encoder architecture underperforms the decoder-based models
  (Chronos/TimesFM/Kronos) already wired and working here."
task_note: "forecasting task only — embeddings/anomaly_detection/imputation not implemented"
predictions: {
  1: {point: 142.25, p10: 141.05, p90: 143.45, actual_close: 142.80, hit: true, pinball_loss: 0.12, close_sq_error: 0.30, close_abs_error: 0.55},
  2: {point: 142.50, p10: 140.60, p90: 144.40, actual_close: 143.10, hit: true, pinball_loss: 0.17, close_sq_error: 0.36, close_abs_error: 0.60},
  3: {point: 142.75, p10: 140.20, p90: 145.30, actual_close: 145.90, hit: false, pinball_loss: 0.26, close_sq_error: 9.92, close_abs_error: 3.15},
  4: {point: 143.00, p10: 139.85, p90: 146.15, actual_close: 144.00, hit: true, pinball_loss: 0.21, close_sq_error: 1.00, close_abs_error: 1.00},
  5: {point: 143.25, p10: 139.55, p90: 146.95, actual_close: 141.20, hit: true, pinball_loss: 0.30, close_sq_error: 4.20, close_abs_error: 2.05}
}
```

**After aggregation (queryable key, per horizon step):**

```
NY-MARKETHOURS-1330-2000-1D-STEP1 = 88% CI-coverage, avg pinball 0.14, RMSE 0.58, MAE 0.52 (n=912)
NY-MARKETHOURS-1330-2000-1D-STEP5 = 71% CI-coverage, avg pinball 0.33, RMSE 2.35, MAE 1.91 (n=912)
```

## 5) Storage, querying, API shape

- **Layer 1 — raw tagged rows**: one row per walk-forward evaluation,
  tagged per the shared rule, predictions nested as a dict keyed 1-5,
  `model_backend`/`fallback_reason`/`task_note` stored on every row.
- **Layer 2 — precomputed common keys**: session + subsession + timeframe
  + horizon_step, each carrying `n`, CI-coverage, average pinball loss,
  RMSE, MAE.
- **Layer 3 — on-demand query service**: same shared service as every
  other angle.

Reuses the exact same 3-layer architecture and nested-predictions storage
pattern already defined for lag_llama/moirai — no new storage design
needed for this angle.

## 6) What we will achieve / how to use it

- An honest, backtested number for the drift-based fallback proxy —
  the cheapest and simplest of the three quantile-emitting fallback
  angles, useful as a bottom-of-the-barrel comparison point against
  lag_llama's AR(5) and moirai's AR(3).
- A documented, researched reason this angle stops here — so nobody
  later re-opens "should we wire real MOMENT" without first seeing that
  the actual literature was already checked and said no, rather than the
  build error looking like the only obstacle.
- Since storage/tagging/query design is shared, this angle still slots
  into the same cross-angle comparison infrastructure as every other
  angle, despite not being a priority for real-weights investment.

## 7) Deeper rationale

**Why real-weights wiring is a considered "no," not a deferred "later":**
researched directly (not assumed) — MOMENT's own published review
states plainly that "forecasting isn't MOMENT's strongest point": it
underperforms PatchTST on long-term forecasting benchmarks and is only
competitive (not best) short-term. It's explicitly described as
**undertrained relative to its peers** — trained on meaningfully less
data than TimesFM, MOIRAI, and Chronos, with no synthetic-data
augmentation used, unlike those competitors. Where MOMENT actually shows
strength is classification (beat other foundation models zero-shot on
the UCR archive) and multi-task scenarios combining forecasting with
anomaly detection — neither of which this angle implements. A broader
2026 benchmarking survey also found masked-**encoder** architectures
(MOMENT's and MOIRAI's family) are generally outperformed by
decoder-only/encoder-decoder models on forecasting specifically — and
this project already has three real, working decoder-based foundation
models (Chronos, TimesFM, Kronos). Given all of that, fixing the Python
3.12 build issue would unlock a model that, by its own literature, isn't
expected to add much over what's already wired.

**Why the fallback proxy is still worth backtesting despite that:** the
"no" is about chasing the real pretrained model, not about whether this
angle has any value at all. The honestly-labeled drift-based proxy is
still a real, cheap, comparably-evaluated forecaster — worth including
in the same cross-angle comparison as every other angle, the same way a
naive baseline is worth running even though nobody expects it to win.

**Why this is a firmer call than moirai's "on hold":** moirai's real
blocker included a structural interface mismatch (any-variate attention
literally couldn't be exercised through this codebase regardless of
fixes) — a technical constraint that could theoretically change if the
interface changes. MOMENT's blocker is just a Python-version build
issue, technically the easiest of the three to fix — but the decision
here isn't blocked on feasibility, it's a judgment call informed by the
model's own published track record. That makes it a settled research
conclusion, not a pending technical fix.

**If MOMENT is ever worth revisiting:** it would more plausibly be for
its **anomaly-detection** capability applied to price series (a genuinely
different, currently-uncovered use case in this project, and the task
MOMENT was more competitively benchmarked on) — not as a forecasting
upgrade. That would be a new angle proposal, not a revival of this one.

**Open/unresolved:** none on the decision itself — it's settled. The
only open item is generic to all TSFM benchmark literature: a 2026
benchmarking survey found reported TSFM advantages are often inflated by
pretraining-data leakage into evaluation sets (47-184% apparent
advantage when leaked, vs. 0.3-14% on clean data) — so even the
literature this decision leans on should be read as directionally
informative, not as precise numbers to bet the project on.
