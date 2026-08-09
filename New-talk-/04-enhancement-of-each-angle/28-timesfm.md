---
name: angle-28-timesfm
status: decided
purpose: discussion and enhancement proposal for the `timesfm` angle. Reference implementation lives at `../../vinu-components/vinu-initial-analysis/vinu_initial_analysis/angles/timesfm/`.
---

# 28 — timesfm

**Title (from spec.yaml):** TimesFM Time-Series Foundation Model

## 1) Status

- Discussed: 2026-08-08
- Status: decided (design settled, not yet built)
- Reference implementation verified against real code: `compute.py` /
  `spec.yaml` at
  `vinu-components/vinu-initial-analysis/vinu_initial_analysis/angles/timesfm/`.
- **Real pretrained weights, correctly and currently documented** —
  unlike `timer_timerxl`, this angle's `spec.yaml`/docstring are already
  accurate: `google/timesfm-2.5-200m-pytorch` (200M params) loads via
  the real, genuinely-installable `timesfm[torch]` PyPI package,
  confirmed to not require jax/flax (so it doesn't disturb the shared
  env's torch build). `model_backend: "pretrained"` is the normal path;
  `fallback_proxy` (linear-trend + residual-normal quantiles) only
  triggers on an actual runtime failure — same dormant-safety-net
  treatment as Chronos/Kronos/timer_timerxl.
- **Real, native quantile output — genuinely different from
  Kronos/timer_timerxl.** Verified against the model card
  (`huggingface.co/google/timesfm-2.5-200m-pytorch`): the model has a
  dedicated, trained quantile head (`use_continuous_quantile_head=True`
  in the code, `fix_quantile_crossing=True`) producing **mean plus 9
  real decile levels (10th through 90th)** — 10 values total, not a
  statistical band bolted on after a point forecast. This means, unlike
  Kronos/timer_timerxl, CI-coverage here tests genuine model confidence,
  not a fabricated spread — treated as a primary metric, not a caveated
  secondary one.
- **Confirmed gap: 7 of the 10 real quantile levels are computed and
  thrown away.** The code only extracts `quantile_fc[0,:,1]` (p10) and
  `quantile_fc[0,:,9]` (p90) from the model's own output — q20 through
  q80 are already computed as part of the same forward pass and
  discarded. Same "computed but discarded" pattern already caught in
  `drawdown_deep_dive`/`shock_personality`.
- **Confirmed gap: the code uses a fraction of the model's own documented
  context capacity.** `MAX_CONTEXT = 256` in the code, but the model's
  own HuggingFace card default example configuration uses
  `max_context=1024` — 4x more than what this angle actually requests.
  (A separate blog source claims the underlying architecture supports up
  to 16,384 timesteps; not used as the basis for a recommendation here
  since it isn't corroborated by the official model card the way 1024
  is.)
- Already correctly framed (kept as-is): a general-purpose, non-finance-
  specific comparison baseline alongside Chronos/Kronos, not a
  first-choice signal — same honest framing already applied to Chronos.
- Shared/common piece this depends on: [common-rule-of-time-slicing-tags.md](common-rule-of-time-slicing-tags.md)

## 2) One-line definition

TimesFM is a ready-made AI model, pretrained once by Google on a huge,
general (not finance-specific) collection of time series, that reads a
stock's recent prices and predicts the next 5 prices along with a
genuine, model-native range of how confident it is at several different
confidence levels — not just one band, though this codebase currently
only keeps the widest one.

## 3) Decided parameters

| Parameter | Decided value | Notes |
|---|---|---|
| Model checkpoint | `google/timesfm-2.5-200m-pytorch` (200M params, code default, kept as-is) | real, correctly documented, no correction needed |
| **Context window — raised** | 1024 (up from the code's `MAX_CONTEXT = 256`) | matches the model's own HuggingFace card default config — the code was using a quarter of the model's documented normal operating context |
| Forecast horizon | 5 steps ahead | code's `HORIZON = 5`, same as Chronos/Kronos/lag_llama/moirai/timer_timerxl |
| **Uncertainty band — all 9 deciles kept, not just p10/p90** | q10, q20, q30, q40, q50, q60, q70, q80, q90, all real model output | closes the confirmed gap — the model already computes all of these in one forward pass; discarding 7 of them was pure waste, same principle as keeping iTransformer's 5 channels or Kronos's full OHLC |
| Primary evaluation metric | CI-coverage: actual close falls inside [q10, q90] (80% band) | unlike Kronos/timer_timerxl, this is genuine native model uncertainty, not a bolted-on spread — treated as primary with no caveat needed |
| Secondary evaluation metric | pinball loss across all 9 real decile levels, per horizon step | same proper-scoring-rule reasoning as lag_llama/moirai, now with genuinely richer resolution (9 real levels instead of 5 lag_llama levels or 2 moirai levels) since this model actually outputs that many |
| Tertiary evaluation metric | RMSE and MAE between the median (q50) and actual close, per horizon step | same "how close in dollars" addition used across every point/quantile-output angle |
| Min observations (N) | 100 candles | raised from the code's real floor (`MIN_OBSERVATIONS = 30`), same cross-angle consistency move; unlike Kronos's context, TimesFM's context isn't a hard per-call requirement, so this is a quality floor, not an architectural one |
| Diagnostic fields stored | `checkpoint`, all 9 decile forecasts, `context_length_used` | real, already-computed fields — kept, not discarded |
| Model backend | `pretrained` in the normal case; `fallback_proxy` only on actual runtime failure | same dormant-fallback treatment as Chronos/Kronos/timer_timerxl |
| Backtest method | walk-forward (rolling predict + check + slide) | same method as every other angle |
| Storage shape | one row per walk-forward evaluation, nested `predictions` dict keyed by horizon step (1-5), each holding all 9 decile values | same nested-dict pattern as Chronos/Kronos/lag_llama/moirai/timer_timerxl |
| Timeframes | 1min, 5min, 15min, 1hr, 4hr, 1day | widened from the spec's current 1D-only, same treatment as the other pretrained angles |
| Date range | 2022-01-01 → 2026-Q2 | same as other angles |
| Data source | Alpaca | same as other angles |
| Baseline comparison | naive random-walk (forecast = last close), same backtest | same rationale as other angles |
| Symbol scope | parameterized — specific ticker or all tracked tickers | same as other angles |
| Time-based tagging | session / day-of-week / week / month / quarter | shared rule, see [common-rule-of-time-slicing-tags.md](common-rule-of-time-slicing-tags.md) |
| Compute cost | open/unbenchmarked, now a real question given the 4x context increase | 200M-param transformer forward pass at 1024 context instead of 256 — meaningfully more expensive per call; needs real measurement before committing to a refit cadence at finer timeframes, same caveat pattern as every other pretrained angle |
| Future work, not decided now | trying an even larger context (up to the model's reported extended capacity) as a speed/accuracy trade-off study | same "future work" framing already used for Kronos's untried checkpoint sizes — flagged, not pursued here, since the larger figure isn't corroborated by the official model card |

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
model_backend: pretrained
checkpoint: google/timesfm-2.5-200m-pytorch
context_length_used: 1024
predictions: {
  1: {q10: 141.20, q20: 141.80, q30: 142.10, q40: 142.30, q50: 142.45, q60: 142.60, q70: 142.80, q80: 143.05, q90: 143.50, actual_close: 142.80, hit: true, pinball_loss: 0.08, close_sq_error: 0.12, close_abs_error: 0.35},
  ...
  5: {q10: 139.40, q20: 140.90, q30: 141.80, q40: 142.60, q50: 143.30, q60: 144.00, q70: 144.80, q80: 145.70, q90: 147.20, actual_close: 141.20, hit: true, pinball_loss: 0.31, close_sq_error: 4.41, close_abs_error: 2.10}
}
```

**After aggregation (queryable key, per horizon step):**

```
NY-MARKETHOURS-1330-2000-1D-STEP1 = 86% CI-coverage, avg pinball 0.10, RMSE 0.51, MAE 0.44 (n=912)
NY-MARKETHOURS-1330-2000-1D-STEP5 = 71% CI-coverage, avg pinball 0.29, RMSE 2.20, MAE 1.79 (n=912)
```

## 5) Storage, querying, API shape

- **Layer 1 — raw tagged rows**: one row per walk-forward evaluation,
  tags applied once per row, predictions nested by horizon step, all 9
  decile values kept per step — same pattern as Chronos/Kronos/
  lag_llama/moirai/timer_timerxl.
- **Layer 2 — precomputed common keys**: session + subsession +
  timeframe + horizon_step, each carrying `n`, CI-coverage, average
  pinball loss (now computed across all 9 real levels), RMSE, MAE.
- **Layer 3 — on-demand query service**: same shared service as every
  other angle, plus the option to query narrower bands (e.g. [q30,q70],
  a 40% interval) directly from the stored deciles without needing a new
  model call.

Reuses the exact same 3-layer architecture and nested-predictions
storage pattern already defined for the other pretrained angles — no new
storage design needed.

## 6) What we will achieve / how to use it

- A real, measured answer to "does TimesFM's zero-shot forecast hold up
  on real price data," directly comparable to Chronos and Kronos since
  all three share the same backtest infrastructure.
- The richest probabilistic output of any angle in this project — 9 real
  quantile levels instead of 2, enabling genuinely fine-grained
  calibration checks (is the model well-calibrated at every decile, not
  just the outer 80% band) that no other angle's real output supports.
- A fairer test of the model's actual capability than the current
  256-context setup gives it — running at a quarter of the model's own
  documented normal context handicaps a foundation model that was
  designed and evaluated at longer context lengths.
- Since this is the third genuinely-pretrained, genuinely-quantile-native
  foundation model in this project (after Chronos and TimesFM's own
  earlier-considered peers), it strengthens the cross-model comparison
  set for "which foundation model actually forecasts price best."

## 7) Deeper rationale

**Why the context window is raised to 1024 specifically, not left at 256
or pushed to the higher, less-verified figure:** 1024 is the model's own
documented default operating configuration, per its official
HuggingFace card — using less than that handicaps the model relative to
how it's actually meant to run; using dramatically more (the 16,384
figure) is only corroborated by a secondary blog source, not the
official model card, so it's flagged as speculative future work rather
than adopted as a decided parameter. 1024 is the defensible, citable
middle ground.

**Why all 9 deciles are kept instead of just p10/p90:** the model
computes all of them in the same forward pass at no extra cost — the
same "don't discard real, free model output" principle applied to every
other angle with unused diagnostic fields (iTransformer's channels,
Kronos's OHLC, TFT's variable-selection weights). Here it has extra
value because it enables genuine pinball-loss evaluation across the full
distribution, not just a single band's coverage.

**Why CI-coverage is primary here, unlike Kronos/timer_timerxl:** those
two models don't natively produce a distribution — their bands are
statistical constructions bolted on after a deterministic point
forecast, so grading them primarily on band coverage would be evaluating
the bolt-on math. TimesFM's quantile head is trained as part of the
model itself (`use_continuous_quantile_head=True`, with an explicit
`fix_quantile_crossing=True` guarantee) — its band is genuine model
output, so CI-coverage genuinely tests the model's own calibration here.

**Why N=100 instead of the code's current 30:** same consistency
reasoning as every other raised-floor angle — note this is a quality
floor, not an architectural requirement the way Kronos's context length
is, since TimesFM's context is flexible rather than fixed.

**Open/unresolved:** the actual compute cost of a 1024-context, 200M-
parameter forward pass across a full walk-forward backtest — especially
at finer timeframes — is unmeasured, same category of open caveat as
ARIMA/Chronos/Kronos/timer_timerxl. Whether an even larger context (up
to the model's reported extended capacity) would meaningfully improve
results is also open, explicitly deferred as future work rather than
guessed at here.
