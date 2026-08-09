---
name: angle-16-moirai
status: decided
purpose: discussion and enhancement proposal for the `moirai` angle. Reference implementation lives at `../../vinu-components/vinu-initial-analysis/vinu_initial_analysis/angles/moirai/`.
---

# 16 — moirai

**Title (from spec.yaml):** MOIRAI Any-Variate Time-Series Foundation Model (fallback proxy)

## 1) Status

- Discussed: 2026-08-07
- Status: decided (design settled, not yet built)
- Reference implementation verified against real code: `compute.py` /
  `spec.yaml` at
  `vinu-components/vinu-initial-analysis/vinu_initial_analysis/angles/moirai/`
- **Currently always `fallback_proxy` — confirmed real**, same as
  lag_llama: `compute.py` hardcodes `"model_backend": "fallback_proxy"`
  on every successful row, no conditional pretrained path exists.
- **Two independent reasons real weights aren't wired — and this is
  where it differs from lag_llama:**
  1. **Same class of environment blocker.** Per
     `../03-initial-analysis-check-architectural-test/03-actual-plan-findings/06-models-download.md`:
     `uni2ts` (Salesforce's real loader package, confirmed to exist on
     PyPI) requires `torch==2.4.1`, which would downgrade the shared
     env's `torch 2.13.0+cpu` (plus pull in jax/jaxlib/pytorch-lightning/
     tensorboard), risking the 5 already-wired real loaders. The weights
     themselves (`Salesforce/moirai-1.0-R-small`) are already downloaded
     into `data/models/`.
  2. **A structural mismatch, independent of the dependency issue.**
     This codebase's `runner.py` calls `compute()` once per single
     `symbol` — no multi-ticker batching is exposed anywhere at that
     interface. MOIRAI's actual differentiator is **any-variate joint
     attention across multiple series at once**; called one symbol at a
     time, it would degrade to single-variate regardless of whether real
     weights loaded — the same degeneration Chronos/TimesFM already
     accept for their own (non-any-variate) use here.
- **Decision: real-weights wiring is on hold, not tracked as scoped
  future work.** Unlike lag_llama (a pure environment blocker with a
  clear, scoped fix), this angle has a second, structural blocker that a
  dependency fix alone wouldn't resolve — exercising MOIRAI's actual
  selling point would also need a runner-level interface change to accept
  multiple symbols in one call. Given that, this was decided to be left
  on hold rather than framed as "just needs the env fixed later." If the
  runner interface ever changes to support multi-symbol calls, this
  would need to be revisited as a fresh decision, not resumed as-is.
- Shared/common piece this depends on: [common-rule-of-time-slicing-tags.md](common-rule-of-time-slicing-tags.md),
  applied unchanged.

## 2) One-line definition

MOIRAI, as this codebase actually runs it today, is not the real
pretrained AI model — it's a simple statistical formula that looks at a
stock's recent price moves, fits a straight-line pattern through them,
and forecasts the next 5 moves with a rough range attached, standing in
for a real model whose signature ability (reasoning about many stocks
jointly at once) this project's current setup couldn't use anyway, even
if it were wired in.

## 3) Decided parameters

| Parameter | Decided value | Notes |
|---|---|---|
| Model backend | always `fallback_proxy` | confirmed from code — no conditional path exists; every stored row carries this label plus `fallback_reason` and `any_variate_note` |
| Underlying fallback method | AR(3): OLS fit of next return on its own 3 lags (`AR_ORDER = 3`) | code's real method — simpler than lag_llama's AR(5), matching the real MOIRAI's own comparatively simpler per-call footprint |
| Min observations (N) | 100 candles | raised from the code's current floor (`MIN_OBSERVATIONS = 20`), same consistency move as every other angle |
| Forecast horizon | 5 steps ahead | code's `HORIZON = 5`, same as lag_llama/Chronos/Kronos |
| Uncertainty band | point forecast + p10/p90 (single 80% interval) | code's real, exposed output — narrower than lag_llama's 5-level quantile set; only 2 quantile levels are actually computed (`1.2816` z-value = 90th percentile) |
| Primary evaluation metric | CI-coverage: actual close falls inside [p10, p90] | same principle as ARIMA/lag_llama — use the model's own real band as the hit criterion; this is an 80% band, not 90%/95% — the code only ever computes these two levels |
| Secondary evaluation metric | pinball loss on the 2 available quantile levels (0.10, 0.90), per horizon step | same proper-scoring-rule reasoning as lag_llama, applied to whatever real quantiles the code actually outputs — here just 2, not 5 |
| Tertiary evaluation metric | RMSE and MAE between point forecast and actual close, per horizon step | same "how close in dollars" addition as lag_llama/Kronos/LPatchTST/LSTM |
| Diagnostic fields stored | point forecast, p10, p90, actual close, hit (in-band), pinball loss (per quantile level), close_sq_error, close_abs_error — per horizon step | same reasoning as other angles — store exactly what the model gives, nothing invented |
| Backtest method | walk-forward (rolling refit + forecast + check, slide forward) | same method as all other angles |
| Storage shape | one row per walk-forward evaluation, nested `predictions` dict keyed by horizon step (1-5), each holding point/p10/p90/hit/pinball_loss/close_sq_error/close_abs_error | same nested-dict pattern as lag_llama/Chronos/Kronos |
| Timeframes | 1min, 5min, 15min, 1hr, 4hr, 1day | widened from the spec's current 1D-only, same as every other angle |
| Date range | 2022-01-01 → 2026-Q2 | same as other angles |
| Data source | Alpaca | same as other angles |
| Baseline comparison | naive random-walk (forecast = last close), same backtest | same rationale as other angles |
| Symbol scope | parameterized — specific ticker or all tracked tickers; **always single-ticker per call, any-variate mode never exercised** | code's real interface constraint, carried through honestly rather than glossed over |
| Time-based tagging | session / day-of-week / week / month / quarter | shared rule, see [common-rule-of-time-slicing-tags.md](common-rule-of-time-slicing-tags.md) |
| Compute cost | cheap, not a concern | closed-form OLS solve per step (3x3 system) — negligible, same class as lag_llama |
| Real-weights path | **on hold, not scheduled, not treated as scoped future work** | two independent blockers (env dependency + structural any-variate mismatch) — see §1; distinct from lag_llama's single, scoped blocker |

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
fallback_reason: "uni2ts would downgrade torch 2.13.0+cpu -> 2.4.1 in
  the shared env plus pull in jax/lightning; additionally this angle's
  per-symbol compute() call can't exercise MOIRAI's any-variate
  multi-ticker mechanism anyway. On hold, not scoped future work."
any_variate_note: "single-ticker only call; any-variate mechanism not
  exercised, this is the single-variate degenerate case"
predictions: {
  1: {point: 142.30, p10: 141.10, p90: 143.50, actual_close: 142.80, hit: true, pinball_loss: 0.11, close_sq_error: 0.25, close_abs_error: 0.50},
  2: {point: 142.60, p10: 140.70, p90: 144.50, actual_close: 143.10, hit: true, pinball_loss: 0.16, close_sq_error: 0.25, close_abs_error: 0.50},
  3: {point: 143.00, p10: 140.30, p90: 145.70, actual_close: 145.90, hit: false, pinball_loss: 0.24, close_sq_error: 8.41, close_abs_error: 2.90},
  4: {point: 143.40, p10: 140.00, p90: 146.80, actual_close: 144.00, hit: true, pinball_loss: 0.19, close_sq_error: 0.36, close_abs_error: 0.60},
  5: {point: 143.80, p10: 139.70, p90: 147.90, actual_close: 141.20, hit: true, pinball_loss: 0.29, close_sq_error: 6.76, close_abs_error: 2.60}
}
```

**After aggregation (queryable key, per horizon step):**

```
NY-MARKETHOURS-1330-2000-1D-STEP1 = 89% CI-coverage, avg pinball 0.13, RMSE 0.55, MAE 0.48 (n=912)
NY-MARKETHOURS-1330-2000-1D-STEP5 = 73% CI-coverage, avg pinball 0.31, RMSE 2.28, MAE 1.87 (n=912)
```

(Same expected decay-by-horizon-step pattern as lag_llama/Chronos/Kronos
— a real, measurable finding, not assumed in advance.)

## 5) Storage, querying, API shape

- **Layer 1 — raw tagged rows**: one row per walk-forward evaluation,
  tagged per the shared rule, predictions nested as a dict keyed 1-5 as
  shown in §4. `model_backend`, `fallback_reason`, and `any_variate_note`
  stored on every row — never omitted.
- **Layer 2 — precomputed common keys**: session + subsession + timeframe
  + horizon_step combinations precomputed after each run, each carrying
  `n`, CI-coverage, average pinball loss, RMSE, MAE.
- **Layer 3 — on-demand query service**: same shared service as every
  other angle, unpacks the nested `predictions` dict for custom key
  combinations.

Reuses the exact same 3-layer architecture and nested-predictions storage
pattern already defined for lag_llama/Chronos/Kronos — no new storage
design needed for this angle.

## 6) What we will achieve / how to use it

- An honest, backtested answer to "how good is the simple AR(3) stand-in"
  — clearly separated by `model_backend: fallback_proxy` from the
  genuinely-pretrained angles.
- A direct comparison against lag_llama's own fallback proxy (both AR-
  based, both quantile-emitting, different orders/band widths) — a
  natural same-category comparison once both are built.
- A permanent, honest record (`any_variate_note`) that this angle's core
  differentiator was never actually exercised here — so nobody
  downstream mistakes a single-ticker AR(3) backtest for a validated
  test of MOIRAI's real any-variate capability.
- Since storage/tagging/query design is shared, this angle's backtest
  slots directly into the same cross-angle comparison infrastructure as
  every other angle, once built.

## 7) Deeper rationale

**The real model, for reference only — this does not change today's
design, and unlike lag_llama, is not treated as a near-term wiring
target:**

- **Architecture**: encoder-only masked Transformer (Salesforce), unlike
  the decoder-only designs of Chronos/Kronos/lag_llama. Trained on LOTSA
  — 27 billion observations across 9 domains.
- **Any-variate attention**: flattens multiple time series into a single
  sequence, using rotary position embeddings for time and learned binary
  attention biases to mark which variate each token belongs to — lets
  one model call jointly attend across many series (e.g. many tickers)
  at once. This is MOIRAI's actual selling point.
- **Output**: a flexible mixture-distribution forecast (more expressive
  than a fixed quantile set or single Student-t), from which point/
  quantile forecasts are derived.
- **Sizes**: Small (14M params, `Salesforce/moirai-1.0-R-small` — the
  variant already downloaded here), Base (91M), Large (311M).

**Why this angle's real-weights path is "on hold," not "future work"
like lag_llama's:** lag_llama has exactly one blocker (an environment
dependency conflict) with a clear resolution path (isolate the
dependency, wire the real weights, done). MOIRAI has that same class of
blocker *plus* a second, structural one — its actual differentiator
can't be exercised through this codebase's current per-symbol interface
at all, regardless of dependency resolution. Framing it as "just needs
the env fixed" would overstate how close this angle actually is to being
meaningfully different from what the fallback already tests. Revisiting
it would require a real interface-level decision (should `compute()`
support multi-symbol batching?) that's out of scope for this angle-by-
angle discussion.

**Why the fallback proxy is still worth backtesting seriously:** even
though it can never validate MOIRAI's actual differentiator, the AR(3) +
80%-band proxy is a genuine, honestly-labeled probabilistic forecaster in
its own right — same reasoning as lag_llama — and gives a real second
data point (alongside lag_llama's AR(5)) on how a simple statistical
baseline performs when asked to mimic a foundation model's output shape.

**Why pinball loss on only 2 quantile levels instead of skipping it:**
pinball loss is well-defined for any number of quantile levels, not just
5 — using it here on the 2 levels the code actually computes (p10, p90)
keeps the metric consistent with lag_llama's approach rather than
dropping it just because this angle exposes a narrower band.

**Why N=100 instead of the code's current 20:** same consistency
reasoning as every other raised-floor angle — this code's floor (20) is
even lower than lag_llama's (25), for the same simple-AR-fit reason, but
kept uniform at 100 for fair cross-angle/cross-timeframe comparison.

**Open/unresolved:** both blockers are real and independently verified —
the dependency conflict from `06-models-download.md`, and the
any-variate/single-symbol mismatch confirmed directly from
`runner.py`'s `_run_angle` call pattern. Neither is expected to be
revisited without a deliberate, separate decision (an isolated
environment for dependency-conflicted angles, and/or a runner interface
change to support multi-symbol calls) — this file does not assume either
will happen.
