---
name: angle-27-timer_timerxl
status: decided
purpose: discussion and enhancement proposal for the `timer_timerxl` angle. Reference implementation lives at `../../vinu-components/vinu-initial-analysis/vinu_initial_analysis/angles/timer_timerxl/`.
---

# 27 — timer_timerxl

**Title (from spec.yaml):** Timer / Timer-XL Patch-Based Foundation Model (fallback proxy)

## 1) Status

- Discussed: 2026-08-08
- Status: decided (design settled, not yet built)
- Reference implementation verified against real code: `compute.py` /
  `spec.yaml` at
  `vinu-components/vinu-initial-analysis/vinu_initial_analysis/angles/timer_timerxl/`.
- **Real pretrained weights, actually loaded and used by default —
  same category as Chronos/Kronos, not lag_llama/moirai/moment.**
  `_get_model()` loads `thuml/timer-base-84m` via
  `AutoModelForCausalLM.from_pretrained(..., trust_remote_code=True)`
  from the shared `data/models/` directory (per
  `06-models-download.md`'s "Wired since — 2 more angles now run real
  pretrained weights" section, alongside `kronos`). `model_backend:
  "pretrained"` is the normal-path result; `fallback_proxy` only
  triggers inside a broad `except Exception` if the real load/inference
  actually fails at runtime (missing weights, transformers version
  issue) — same dormant-safety-net treatment already established for
  Chronos/Kronos, not designed around here since real weights are
  confirmed present.
- **Real model, verified against the actual paper** (Wu, Hu, Liu, Wu,
  Wang, Long, *"Timer: Generative Pre-trained Transformers Are Large
  Time Series Models,"* ICML 2024; HF `thuml/timer-base-84m`): 84M
  parameters, decoder-only causal Transformer, 8 layers, pretrained on
  260B time points, patch length 96, context length up to 2880 — all
  of which match the code's own constants (`PATCH_SIZE = 96`,
  `MAX_CONTEXT = 2880`) exactly.
- **A real, fixable documentation bug found and worth flagging
  explicitly**: this angle's own `spec.yaml` title still says
  "(fallback proxy)" and its purpose text claims "neither package name
  exists on PyPI... isn't pip-installable" — both stale, left over from
  before the 2026-08-06 wiring pass. `06-models-download.md` documents
  that `kronos`'s `spec.yaml` **was** updated to drop the "(fallback
  proxy)" title in that same pass; `timer_timerxl`'s apparently wasn't.
  Recommended fix, noted here rather than silently worked around:
  update `spec.yaml`'s title/purpose to match `kronos`'s treatment.
- **A real, minor code inconsistency found**: `MIN_OBSERVATIONS = 24` in
  the code is set well below the real model's actual hard requirement
  (`PATCH_SIZE = 96` — at least one full patch needed). Between 24 and
  95 observations, the code passes its own `insufficient_data` check,
  then attempts real-model inference, hits `n_patches < 1`, raises, and
  silently falls through to the fallback proxy — not a silent lie (the
  real exception detail is captured in `fallback_reason`), but an
  avoidable, confusing path. Raising the floor to 100 (see §3) also
  happens to cleanly fix this, since 100 > 96.
- Shared/common piece this depends on: [common-rule-of-time-slicing-tags.md](common-rule-of-time-slicing-tags.md)

## 2) One-line definition

Timer is a ready-made AI model, pretrained once on 260 billion real time
points from many domains, that reads a stock's recent prices in fixed
96-point chunks and predicts the next 5 chunks' worth of prices — a
single best-guess path, not a range, though this codebase adds a rough
range around that guess after the fact.

## 3) Decided parameters

| Parameter | Decided value | Notes |
|---|---|---|
| Model checkpoint | `thuml/timer-base-84m` (84M params) | code's real default, matches the actual downloaded weights — Timer-XL (long-context variant) isn't what's actually loaded, despite the angle's name; kept as-is since this is the checkpoint that's real and present |
| Patch size / context | 96 / up to 2880 (code constants, kept as-is) | hard architectural requirements verified against the real paper — same "fixed ceiling" treatment as Chronos's 512 limit / Kronos's 512 context |
| Forecast horizon | 5 steps ahead | code's `HORIZON = 5`, same as Chronos/Kronos/lag_llama/moirai |
| Uncertainty band | point forecast + p10/p90, **not native model uncertainty** | the real Timer model is a deterministic point forecaster (confirmed in the code's own docstring) — the p10/p90 band is a post-hoc residual-normal log-return spread bolted on around the point forecast, the same construction technique used in lag_llama/moirai's fallback proxies, not something Timer itself outputs |
| Primary evaluation metric | directional accuracy on `close`, per horizon step | same reasoning as Kronos — the real model has no native uncertainty output, so (per the precedent already set there) evaluation centers on what the model actually, natively produces: a point forecast |
| Secondary evaluation metric | RMSE and MAE between point forecast and actual close, per horizon step | same "how close in dollars" addition used across every point-output angle |
| Tertiary evaluation metric | CI-coverage on the [p10, p90] band, **explicitly caveated** | this tests whether the *bolted-on statistical spread* is well-calibrated — not whether Timer's own uncertainty is good, since it has none; kept as a secondary check since the band is real, already-computed output, just not evaluated as if it were the model's genuine confidence |
| Min observations (N) | 100 candles | raised from the code's real floor (`MIN_OBSERVATIONS = 24`) — both the standard cross-angle consistency move and a direct fix for the sub-patch fallback-trigger quirk noted in §1, since 100 clears the real 96-point patch requirement |
| Diagnostic fields stored | `checkpoint`, `patch_size`, `n_patches`, full point/p10/p90 per horizon step | real, already-computed fields — kept, not discarded |
| Model backend | `pretrained` in the normal case; `fallback_proxy` only if real inference actually fails at runtime | same dormant-fallback treatment as Chronos/Kronos — not designed around here |
| Backtest method | walk-forward (rolling predict + check + slide) | same method as every other angle |
| Storage shape | one row per walk-forward evaluation, nested `predictions` dict keyed by horizon step (1-5) | same nested-dict pattern as Chronos/Kronos/lag_llama/moirai |
| Timeframes | 1min, 5min, 15min, 1hr, 4hr, 1day | widened from the spec's current 1D-only, same treatment as Chronos/Kronos |
| Date range | 2022-01-01 → 2026-Q2 | same as other angles |
| Data source | Alpaca | same as other angles |
| Baseline comparison | naive random-walk (forecast = last close), same backtest | same rationale as other angles |
| Symbol scope | parameterized — specific ticker or all tracked tickers | same as other angles |
| Time-based tagging | session / day-of-week / week / month / quarter | shared rule, see [common-rule-of-time-slicing-tags.md](common-rule-of-time-slicing-tags.md) |
| Compute cost | open/unbenchmarked | 84M-param transformer forward pass — similar cost class to Kronos, not yet measured across finer timeframes, same honesty caveat applied throughout |
| **Recommended fix, not part of the backtest design itself** | update `spec.yaml`'s title/purpose to drop "(fallback proxy)" and the stale PyPI claim, matching the fix already applied to `kronos`'s spec | a documentation correction, flagged for whoever does the actual build pass |

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
checkpoint: thuml/timer-base-84m
patch_size: 96
n_patches: 1
predictions: {
  1: {point: 142.35, p10: 141.10, p90: 143.60, actual_close: 142.80, hit: true, in_band: true, close_sq_error: 0.20, close_abs_error: 0.45},
  2: {point: 142.70, p10: 140.80, p90: 144.60, actual_close: 143.10, hit: true, in_band: true, close_sq_error: 0.16, close_abs_error: 0.40},
  3: {point: 143.10, p10: 140.60, p90: 145.60, actual_close: 145.90, hit: true, in_band: false, close_sq_error: 7.84, close_abs_error: 2.80},
  4: {point: 143.50, p10: 140.40, p90: 146.60, actual_close: 144.00, hit: false, in_band: true, close_sq_error: 0.25, close_abs_error: 0.50},
  5: {point: 143.90, p10: 140.20, p90: 147.60, actual_close: 141.20, hit: false, in_band: true, close_sq_error: 7.29, close_abs_error: 2.70}
}
```

**After aggregation (queryable key, per horizon step):**

```
NY-MARKETHOURS-1330-2000-1D-STEP1 = 68% directional accuracy, RMSE 0.52, MAE 0.47, 84% CI-coverage (n=912)
NY-MARKETHOURS-1330-2000-1D-STEP5 = 55% directional accuracy, RMSE 2.31, MAE 1.85, 69% CI-coverage (n=912)
```

## 5) Storage, querying, API shape

- **Layer 1 — raw tagged rows**: one row per walk-forward evaluation,
  tags applied once per row, predictions nested by horizon step, same
  pattern as Chronos/Kronos/lag_llama/moirai.
- **Layer 2 — precomputed common keys**: session + subsession +
  timeframe + horizon_step, each carrying `n`, directional accuracy,
  RMSE, MAE, and CI-coverage (with its calibration caveat carried in
  documentation, not the data itself).
- **Layer 3 — on-demand query service**: same shared service as every
  other angle.

Reuses the exact same 3-layer architecture and nested-predictions
storage pattern already defined for Chronos/Kronos — no new storage
design needed.

## 6) What we will achieve / how to use it

- A real, measured answer to "does Timer's zero-shot forecast hold up on
  real price data," directly comparable to Chronos and Kronos since all
  three are genuinely pretrained foundation models sharing the same
  backtest infrastructure.
- A corrected understanding of this angle's actual status — real
  pretrained, not fallback — closing a documentation gap that could
  otherwise mislead anyone reading `spec.yaml` alone.
- An honest separation between "does the model call the right direction"
  (what Timer actually does) and "is the bolted-on uncertainty band
  trustworthy" (a separate, secondary question) — rather than treating a
  fabricated band as if it were genuine model confidence.

## 7) Deeper rationale

**Why directional accuracy is primary, not CI-coverage, despite this
angle already having a p10/p90 field to work with:** this mirrors the
exact reasoning already established for Kronos — the real model doesn't
natively produce a distribution, so grading it primarily on a band it
never actually generated would be evaluating the bolt-on math, not the
model. The difference from Kronos is that here the bolt-on band is
already computed and stored as real output, so it's kept and reported —
just not treated as the headline metric.

**Why the spec.yaml staleness is worth flagging explicitly instead of
quietly treating the angle as "fine":** the title still reads "(fallback
proxy)" and the purpose text still claims no installable package exists
— both were true before the 2026-08-06 wiring pass and are false now.
Since `kronos` got this exact fix in the same pass (per
`06-models-download.md`), leaving `timer_timerxl` out of sync isn't a
new problem to solve here, but it is worth naming clearly so it doesn't
get missed.

**Why N=100 also fixes a real behavioral quirk, not just a consistency
bump:** unlike most of the N=100 changes in this project (which are pure
cross-angle consistency moves), this one directly closes a gap between
the code's own stated floor (24) and its real architectural requirement
(96) — below 96, the real model can never run, so keeping the floor at
24 just means some requests silently downgrade to the fallback proxy
for no good reason.

**Open/unresolved:** compute cost across finer timeframes is unmeasured,
same caveat as Chronos/Kronos. The recommended `spec.yaml` fix is noted
for the build pass, not applied here (this file is a design discussion,
not a code change).
