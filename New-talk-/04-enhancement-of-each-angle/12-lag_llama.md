---
name: angle-12-lag_llama
status: decided
purpose: discussion and enhancement proposal for the `lag_llama` angle. Reference implementation lives at `../../vinu-components/vinu-initial-analysis/vinu_initial_analysis/angles/lag_llama/`.
---

# 12 — lag_llama

**Title (from spec.yaml):** Lag-Llama Probabilistic Time-Series Model (fallback proxy)

## 1) Status

- Discussed: 2026-08-07
- Status: decided (design settled, not yet built)
- Reference implementation verified against real code: `compute.py` /
  `spec.yaml` at
  `vinu-components/vinu-initial-analysis/vinu_initial_analysis/angles/lag_llama/`
- **Currently always `fallback_proxy` — confirmed real, not a case where
  fallback "might" mix in.** `compute.py` hardcodes
  `"model_backend": "fallback_proxy"` on every successful row; there is no
  pretrained code path in this angle at all (unlike Chronos/Kronos, where
  fallback exists in code but never actually triggers because real
  weights load).
- **A real path to pretrained exists but is deliberately deferred, not
  missing.** Per
  `../03-initial-analysis-check-architectural-test/03-actual-plan-findings/06-models-download.md`
  ("Deferred by decision" section, 2026-08-06): the `lag-llama` checkpoint
  **is already downloaded** into `data/models/` via `make models`. The
  blocker to actually wiring it is a dependency conflict — loading the
  real checkpoint needs `gluonts[torch]<=0.14.4`, which would downgrade
  `pandas 3.0.3 → 2.3.3` in the shared environment (plus
  pytorch-lightning/torchmetrics), risking the 5 already-wired real
  loaders (finbert, chronos, timesfm, timer, kronos). It would also
  require vendoring the research repo's `lag_llama/`, `gluon_utils/`,
  `utils/` model code, since the loader is a raw `.ckpt`, not a pip
  package. This was a deliberate user decision (keep the proxy, document
  the exact blocker) — not the same category as the 4 angles that were
  removed outright for having no checkpoint ever available (`timegpt`,
  `patchformer`, `fincast_foundation_model`, `finmamba_graph_state_space`).
- **Note — the `compute.py` docstring itself is stale.** It currently
  says lag-llama "does not resolve on PyPI... the only public artifact is
  a research repo requiring a manual clone... outside the a-few-minutes
  budget," which was true at the time that module was written, but is now
  superseded: the checkpoint *was* successfully downloaded in the later
  models-download pass. The real, current blocker is the dependency
  conflict described above, not artifact unavailability. Worth correcting
  the docstring's framing when this angle is actually built.
- **Real model, verified via the paper/HF card, for future-reference when
  wiring happens** (arXiv:2310.08278, HF
  `time-series-foundation-models/Lag-Llama`) — see §7 for full detail:
  2.45M params, Student-t distributional output via autoregressive
  trajectory sampling, trained at context length 32 (works up to 1024 at
  inference), input built from lag features + datetime/summary-stat
  covariates, not raw price windows. None of this changes today's proxy
  design — it's documented so the eventual real-weights wiring has a
  known target instead of needing re-research.
- Shared/common piece this depends on: [common-rule-of-time-slicing-tags.md](common-rule-of-time-slicing-tags.md),
  applied unchanged (see that file's Tag 1-5 / storage-layer rules).

## 2) One-line definition

Lag-Llama, as this codebase actually runs it today, is not the real
pretrained AI model — it's a simple statistical formula that looks at a
stock's last 5 price moves, fits a straight-line pattern through them,
and forecasts the next 5 moves as a spread of possible prices (a range,
not just one guess), standing in for the real model until an environment
conflict blocking it is resolved.

## 3) Decided parameters

| Parameter | Decided value | Notes |
|---|---|---|
| Model backend | always `fallback_proxy` | confirmed from code — no conditional path exists here, unlike Chronos/Kronos where fallback is dormant; every stored row carries this label plus `fallback_reason` so it's never confused with a real pretrained result |
| Underlying fallback method | AR(5): OLS fit of next return on its own 5 lags (`LAG_ORDER = 5`) | code's real method — literally the "lag" part of the name, per the module docstring |
| Min observations (N) | 100 candles | code's current floor is `MIN_OBSERVATIONS = 25` — raised to 100 to match ARIMA's decided floor, keeping every angle's backtest starting from the same warm-up window for fair cross-angle comparison, even though a 5-coefficient OLS fit alone would need far fewer points |
| Forecast horizon | 5 steps ahead | code's `HORIZON = 5` — same horizon length as Chronos/Kronos, kept for cross-angle comparability |
| Uncertainty band | 5-quantile Gaussian: p5 / p25 / p50 / p75 / p95 | code's real, exposed output (`QUANTILE_LEVELS`) — genuinely probabilistic, unlike Kronos which exposes no band at all; spread grows by `sqrt(step)` per horizon step. Gaussian, not the real model's Student-t — see §7 |
| Primary evaluation metric | CI-coverage: actual close falls inside the [p5, p95] band | same principle as ARIMA — use the model's own real quantile output as the hit criterion; this is a 90% band (not 95% like ARIMA), see §7 for why |
| Secondary evaluation metric | average pinball (quantile) loss across all 5 quantile levels, per horizon step | proper scoring rule for the full quantile forecast — checks all 5 levels are individually well-calibrated, not just the outer band |
| Tertiary evaluation metric | RMSE and MAE between forecasted median (p50) and actual close, per horizon step | direct "how close in dollars" answer — CI-coverage and pinball loss both grade calibration, neither says how far off the point forecast actually was; same addition already made for Kronos (RMSE alongside directional accuracy) |
| Diagnostic fields stored | forecasted values at all 5 quantile levels, `point_forecast` (code's raw central path == p50), actual close, hit (in-band), per-quantile pinball loss, per-step squared error (`close_sq_error`, for RMSE) and absolute error (`close_abs_error`, for MAE) — per horizon step | model already computes all 5 quantiles per step; discarding p25/p75 would throw away free, real output, same reasoning as iTransformer/Kronos keeping full model output |
| Backtest method | walk-forward (rolling refit + forecast + check, slide forward) | same method as all other angles |
| Storage shape | one row per walk-forward evaluation, nested `predictions` dict keyed by horizon step (1-5), each holding the 5 quantile values + actual_close + hit + pinball_loss + close_sq_error + close_abs_error | same nested-dict pattern as Chronos/Kronos §5 |
| Timeframes | 1min, 5min, 15min, 1hr, 4hr, 1day | widened from the spec's current 1D-only (`time_formats: [1D]`), same widening already done for ARIMA/Chronos/Kronos |
| Date range | 2022-01-01 → 2026-Q2 | same as other angles |
| Data source | Alpaca | same as other angles |
| Baseline comparison | naive random-walk (forecast = last close), same backtest, same 3 metrics computed on it | same rationale as ARIMA/Chronos/Kronos — without this, a good-looking RMSE/coverage number can't be told apart from "prices barely moved that day" |
| Symbol scope | parameterized — specific ticker or all tracked tickers | same as other angles |
| Time-based tagging | session / day-of-week / week / month / quarter, UTC-based, per shared rule | see [common-rule-of-time-slicing-tags.md](common-rule-of-time-slicing-tags.md) — applied unchanged, no angle-specific variation |
| Compute cost | cheap, not a concern | closed-form OLS solve per step (5x5 system) — negligible next to Kronos/Chronos's 100M+-param transformer forward passes |
| Future real-weights path | tracked, not scheduled | once the shared-env dependency risk is resolved, this angle could be re-wired to the real 2.45M-param checkpoint already sitting in `data/models/` — a separate future revision of this file |

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
fallback_reason: "gluonts[torch]<=0.14.4 required to load the real
  checkpoint would downgrade pandas 3.0.3->2.3.3 in the shared env,
  risking 5 already-wired pretrained loaders; deferred by decision,
  weights already downloaded in data/models/"
predictions: {
  1: {p5: 141.20, p25: 141.90, p50: 142.30, p75: 142.70, p95: 143.40, actual_close: 142.80, hit: true, pinball_loss: 0.09, close_sq_error: 0.25, close_abs_error: 0.50},
  2: {p5: 140.60, p25: 141.70, p50: 142.50, p75: 143.30, p95: 144.40, actual_close: 143.10, hit: true, pinball_loss: 0.14, close_sq_error: 0.36, close_abs_error: 0.60},
  3: {p5: 140.10, p25: 141.60, p50: 142.80, p75: 144.00, p95: 145.50, actual_close: 145.90, hit: false, pinball_loss: 0.22, close_sq_error: 9.61, close_abs_error: 3.10},
  4: {p5: 139.70, p25: 141.50, p50: 143.10, p75: 144.70, p95: 146.50, actual_close: 144.00, hit: true, pinball_loss: 0.18, close_sq_error: 0.81, close_abs_error: 0.90},
  5: {p5: 139.30, p25: 141.40, p50: 143.40, p75: 145.40, p95: 147.60, actual_close: 141.20, hit: true, pinball_loss: 0.27, close_sq_error: 4.84, close_abs_error: 2.20}
}
```

**After aggregation (queryable key, per horizon step):**

```
NY-MARKETHOURS-1330-2000-1D-STEP1 = 91% CI-coverage, avg pinball 0.11, RMSE 0.58, MAE 0.51 (n=912)
NY-MARKETHOURS-1330-2000-1D-STEP5 = 76% CI-coverage, avg pinball 0.31, RMSE 2.40, MAE 1.94 (n=912)
```

(Same expected decay-by-horizon-step pattern as Chronos/Kronos — coverage
dropping, pinball loss growing, and RMSE/MAE growing with horizon are
real, measurable findings, not assumed in advance.)

## 5) Storage, querying, API shape

- **Layer 1 — raw tagged rows**: one row per walk-forward evaluation,
  tagged per [common-rule-of-time-slicing-tags.md](common-rule-of-time-slicing-tags.md)
  (session, day-of-week, week-of-month, month, quarter, all UTC-derived
  from `candle_ts`, computed once at storage time). Predictions nested as
  a dict keyed 1-5 as shown in §4, each holding all 5 quantile values +
  hit + pinball_loss + close_sq_error + close_abs_error. `model_backend`
  and `fallback_reason` stored on every row — never omitted, so
  downstream queries can filter/label results as proxy-derived at a
  glance.
- **Layer 2 — precomputed common keys**: session + subsession + timeframe
  + horizon_step combinations precomputed after each run, each carrying
  `n`, CI-coverage, average pinball loss, **RMSE** (`sqrt(mean(close_sq_error))`
  across all rows in the bucket) and **MAE** (`mean(close_abs_error)`).
  RMSE/MAE/pinball loss only make sense as aggregates — always Layer 2/3
  values, never raw per-row summary fields (same rule as Kronos's RMSE).
- **Layer 3 — on-demand query service**: same shared service as
  Chronos/Kronos, unpacks the nested `predictions` dict to answer any
  custom key combination not already in Layer 2 (e.g. adding day-of-week
  or quarter on top of the default session+subsession+timeframe key).
  Every returned key still carries its `n`, per the shared tagging rule —
  a thin slice (few forecasts) stays visible rather than silently
  trusted.

Reuses the exact same 3-layer architecture, nested-predictions storage
pattern, and tagging rule already defined for Chronos/Kronos and the
common tagging file — no new storage design needed for this angle.

## 6) What we will achieve / how to use it

- An honest answer to "how good is the *simple statistical* stand-in
  actually doing," clearly separated by the `fallback_proxy` label from
  the genuinely-pretrained angles (Chronos, Kronos, TimesFM) — results
  are never silently compared as if they came from the same class of
  model.
- A direct, in-dollars answer to "is it close to the real price" via
  RMSE/MAE per horizon step, compared against the naive-baseline's own
  RMSE/MAE — the concrete test of whether this proxy adds any value over
  doing nothing.
- A proper-scoring-rule metric (pinball loss) not yet used by any other
  angle — established here since this is the one angle whose real code
  output is a full 5-level quantile forecast, reusable later if the real
  Lag-Llama gets wired in.
- A concrete, documented reason (not a vague "couldn't get it working")
  for why this angle isn't on real weights yet, plus confirmation the
  weights are already sitting in `data/models/` — re-wiring later is a
  scoped, known task, not a re-investigation.
- Since storage/tagging/query design is shared, this angle's backtest
  slots directly into the same cross-angle comparison infrastructure as
  every other angle, once built.

## 7) Deeper rationale

**The real model, for reference (arXiv:2310.08278, HF
`time-series-foundation-models/Lag-Llama`) — none of this changes the
current proxy design, it's the target for future wiring:**

- **Size**: 2.45M parameters — genuinely tiny, far smaller than Kronos
  (102M) or Chronos-t5-large (710M); closer in scale to a lightweight
  model than a "full LLaMA."
- **Architecture**: LLaMA decoder-only transformer stack (RMSNorm,
  Rotary Positional Encoding), adapted to take numeric lag features
  instead of text tokens.
- **Input, not raw price windows**: each input token is built from a
  fixed set of *lag indices* (e.g. lag-1, lag-2, ..., a-week-ago,
  a-month-ago), not a plain sliding window of recent prices — so a
  single token already encodes multiple lookback horizons at once. Each
  token also carries date-time covariates (second-of-minute through
  quarter-of-year) and per-token summary statistics (mean, variance) of
  the input window.
- **Context length**: trained at 32 timesteps; the model card states
  zero-shot performance generally improves with longer context up to a
  data-specific point, and recommends trying 32/64/128/256/512/1024 at
  inference.
- **Output**: not a point forecast and not fixed quantile levels — a
  **Student-t distribution's parameters** (location/scale/degrees of
  freedom) predicted per step by a dedicated distribution head. Multi-step
  forecasts come from **greedy autoregressive decoding**: sample from the
  distribution, feed the sample back in as the next input, repeat,
  producing many simulated trajectories — quantiles/point forecasts are
  derived from those trajectories at inference time, not computed
  analytically.

**Why the proxy differs from the real model, and why that's an accepted
gap, not an error:** the fallback uses a **Gaussian** band from one
closed-form OLS residual estimate, not the real model's Student-t
(fatter-tailed, better suited to return-like data with outliers) built
from per-step autoregressive sampling. This is flagged explicitly rather
than glossed over — the proxy matches the spec's differentiator in
*shape* (multi-step, genuinely probabilistic output) but not in
*distribution family or mechanism*. Closing this gap means wiring the
real weights, not improving the proxy's math — so it's tracked as future
work (see Future real-weights path in §3), not solved here.

**Why N=100 instead of the code's current 25:** same reasoning as ARIMA
— a floor of 25 is low even for a simple 5-lag OLS fit, and keeping N
uniform at 100 across angles avoids one angle looking artificially
more/less reliable purely because it was evaluated on a shorter warm-up
window than the others.

**Why CI-coverage on [p5, p95] instead of matching ARIMA's exact 95%:**
the fallback proxy's fixed quantile levels (`[0.05, 0.25, 0.5, 0.75,
0.95]`) don't include a 97.5%/2.5% pair, so an exact 95% central interval
isn't producible from real model output without interpolating between
quantiles — inventing values the model didn't actually emit, the exact
thing this project avoids (see Kronos §7). [p5, p95] gives a genuine 90%
interval built entirely from real output. This is a known, open, small
mismatch against ARIMA's 95% CI-coverage number — flagged here rather
than glossed over.

**Why pinball loss as a secondary metric:** CI-coverage on the outer band
only checks whether the *widest* interval is well-calibrated; it says
nothing about the inner quantiles (p25/p75). Pinball loss is the standard
proper scoring rule for quantile forecasts — it scores every quantile
level individually. Same category of decision as adding RMSE to Kronos's
directional accuracy or QLIKE to GARCH.

**Why RMSE/MAE as a third metric:** neither CI-coverage nor pinball loss
answers "how many dollars off was the forecast" — both grade
calibration, not closeness. RMSE (penalizes large misses harder) and MAE
(plain average dollar error) on the median (p50) forecast directly answer
that question, and only mean something when read against the naive
baseline's own RMSE/MAE run through the identical backtest.

**Why this angle's fallback handling is fully in scope (unlike
Chronos/Kronos, where it's explicitly out of scope):** for Chronos and
Kronos, fallback exists in code but never triggers, since real weights
are confirmed loaded. Here it's the opposite: fallback is the *only*
path that currently runs, so `model_backend` and `fallback_reason` aren't
edge-case fields — they're core to every stored row and every query
result, so any downstream consumer can tell at a glance these are proxy
numbers, not real-model numbers.

**Why the fallback proxy is still worth backtesting seriously, not
dismissed as "fake":** the module docstring is explicit that this proxy
was built to preserve the spec's actual differentiator — a genuinely
probabilistic, multi-quantile output — even though the underlying
mechanism (AR(5) OLS) is far simpler than the real 2.45M-param
transformer. Backtesting it honestly answers a real question ("does even
a simple linear/Gaussian model produce well-calibrated, close-enough
forecasts on this data") and gives a genuine baseline to compare a real
Lag-Llama against, if and when it gets wired in.

**Open/unresolved — the real-weights path:** the checkpoint is already
downloaded (`data/models/`), so nothing needs to be re-fetched. What's
open is purely environmental: `gluonts[torch]<=0.14.4` conflicts with
the shared env's `pandas 3.0.3`, and no isolation strategy (separate
venv, sidecar service, etc.) has been decided yet. This was a deliberate
user decision to defer, not an oversight — revisiting it is future work,
not part of this design.
