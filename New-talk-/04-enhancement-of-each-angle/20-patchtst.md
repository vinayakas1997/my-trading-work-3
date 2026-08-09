---
name: angle-20-patchtst
status: decided
purpose: discussion and enhancement proposal for the `patchtst` angle. Reference implementation lives at `../../vinu-components/vinu-initial-analysis/vinu_initial_analysis/angles/patchtst/`.
---

# 20 — patchtst

**Title (from spec.yaml):** PatchTST Channel-Independent Patch Transformer

## 1) Status

- Discussed: 2026-08-07
- Status: decided (design settled, not yet built)
- Reference implementation verified against real code: `compute.py` /
  `spec.yaml` at
  `vinu-components/vinu-initial-analysis/vinu_initial_analysis/angles/patchtst/`
- Genuinely trained-from-scratch every run, same category as DLinear/
  LSTM/LPatchTST — no `model_backend` field exists in this angle's
  output; not a pretrained/fallback situation at all.
- **This is literally LPatchTST's patch branch, run standalone.** Same
  `PatchEncoderBranch` module (`_patch_transformer.py`), same
  LOOKBACK=32/PATCH_LEN=8/STRIDE=4/D_MODEL=16/NHEAD=2 config, same
  MIN_BARS=90/50-epoch training recipe — the only difference from
  LPatchTST is the missing LSTM branch.
- **Kept for a specific reason, not because it's a strong standalone
  signal.** The real benchmark (same source paper as LPatchTST/LSTM,
  Saly-Kaufmann et al., arXiv:2603.01820, Table 2) reports plain
  PatchTST at **Sharpe 0.86, hit rate 54.1%** — mediocre, barely above
  the paper's own "Passive" baseline (Sharpe 0.48, 53.1%), and clearly
  outperformed by both LSTM (1.32, 55.4%) and its own hybrid variant
  LPatchTST (2.32, 57.7%). The paper's own stated conclusion: *"patch
  segmentation alone is insufficient without robust temporal state
  encoding."* This angle is decided **as the control/ablation for
  LPatchTST's comparison** — LPatchTST's own file (13-lpatchtst.md)
  already promises to answer "does the LSTM branch actually help over
  patching alone," and that question has no counterpart to compare
  against without this angle existing. Not pursued as a standalone
  trading signal in its own right.
- Shared/common piece this depends on: [common-rule-of-time-slicing-tags.md](common-rule-of-time-slicing-tags.md)

## 2) One-line definition

PatchTST is a small model that gets freshly trained from scratch every
time it runs — it breaks a stock's recent prices into short overlapping
chunks (like tiles of an image), looks at how those chunks relate to
each other, and uses that to guess the next price; this exact same
"chunk-reading" component is also the patch half of the LPatchTST
hybrid, so running it alone is what lets us prove whether adding an LSTM
memory on top of it (as LPatchTST does) is actually worth it.

## 3) Decided parameters

| Parameter | Decided value | Notes |
|---|---|---|
| Model backend | not applicable — genuinely trained-from-scratch every step | confirmed no `model_backend` field in code's output, same as DLinear/LSTM/LPatchTST |
| Architecture | `PatchEncoderBranch` (patch_len=8, stride=4, d_model=16, nhead=2, 1 transformer layer) → 1 linear head | code default, kept as-is — the exact same branch LPatchTST uses, run standalone with no LSTM branch |
| Lookback window | 32 candles (code default `LOOKBACK`, kept as-is) | matches LPatchTST's config exactly, so the two are directly comparable on the same window shape |
| Min observations (N) | 100 candles | raised from the code's current floor (`MIN_BARS = 90`), same consistency move as every other angle |
| Training epochs | 50 (code default, kept as-is) | matches LPatchTST exactly |
| Random seed | fixed at 42 for the whole backtest | same reproducibility rationale as DLinear/LSTM/LPatchTST |
| Forecast horizon | 1 step ahead | matches the code's actual architecture and the paper's own 54.1%-hit-rate benchmark, which is itself a 1-step number — same reasoning as LPatchTST/LSTM |
| Hit definition | directional accuracy — predicted direction (up/down/flat, ±0.0001 deadband) matches actual next-candle direction | same reasoning as DLinear/LSTM/LPatchTST |
| Secondary evaluation metric | RMSE and MAE between `forecast_price` and actual close | same "how close in dollars" addition as every other point-output angle |
| Purpose of this angle | **ablation/control for LPatchTST**, not a standalone candidate | its own hit rate/Sharpe are expected to be mediocre per the source paper — the actual value is enabling a direct "PatchTST alone vs. PatchTST+LSTM" comparison on our own data |
| Backtest method | walk-forward (rolling: train fresh, forecast, check, slide, repeat) | same method as every other angle |
| Weight storage | every walk-forward step's trained weights saved, `weights_ref` pointer on the row | same pattern as DLinear/LSTM/LPatchTST |
| Timeframes | 1min, 5min, 15min, 1hr, 4hr, 1day | widened from the spec's current 1D-only, same as every other angle |
| Date range | 2022-01-01 → 2026-Q2 | same as other angles |
| Data source | Alpaca | same as other angles |
| Baseline comparison | naive random-walk (forecast = last close), same backtest, same metrics | same rationale as other angles; PatchTST is itself effectively a secondary "baseline" for LPatchTST on top of this |
| Symbol scope | parameterized — specific ticker or all tracked tickers | same as other angles |
| Time-based tagging | session / day-of-week / week / month / quarter | shared rule, see [common-rule-of-time-slicing-tags.md](common-rule-of-time-slicing-tags.md) |
| Compute cost | not expected to be a concern | identical cost profile to LPatchTST's patch branch alone — cheaper than LPatchTST itself since there's no LSTM branch to train |
| Benchmark to compare against | 54.1% directional accuracy, Sharpe 0.86 (real, verified figure — no correction needed here, unlike LSTM/LPatchTST's miscited numbers) | this backtest's own measured hit rate is checked against this, and more importantly against this angle's own LPatchTST counterpart |

## 4) Example — what one result looks like

**Single forecast row (from the walk-forward backtest, before tagging):**

```
symbol: AAPL
timeframe: 1D
candle_ts: 2024-05-15T13:30:00Z
n_train_windows: 58
lookback: 32
n_patches: 7
train_loss: 0.0154
forecast_price: 142.40
forecast_return: 0.00105
direction: up
actual_close: 142.80
actual_direction: up
hit: true
close_sq_error: 0.16
close_abs_error: 0.40
weights_ref: AAPL_1D_2024-05-15T13-30-00Z.pt
```

**After tagging** (per [common-rule-of-time-slicing-tags.md](common-rule-of-time-slicing-tags.md)):

```
+ session: ny
+ subsession: markethours
+ day_of_week: Wednesday
+ week_of_month: 3
+ month: May
+ quarter: Q2
```

**After aggregation (queryable key):**

```
NY-MARKETHOURS-1330-2000-1D = 54.6% directional accuracy, RMSE 0.79, MAE 0.61 (n=912 forecasts)
```

**The actual point of this angle — the comparison it exists to enable:**

```
NY-MARKETHOURS-1330-2000-1D  patchtst   = 54.6% directional accuracy, Sharpe-equivalent ~0.8x
NY-MARKETHOURS-1330-2000-1D  lpatchtst  = 58.9% directional accuracy, Sharpe-equivalent ~2.2x
→ LSTM branch adds real value on our own data, consistent with the source paper's own finding
```

(Illustrative — the actual gap is what this backtest measures, not assumed
in advance to match the paper exactly.)

## 5) Storage, querying, API shape

- **Layer 1 — raw tagged rows**: same shape as DLinear/LSTM/LPatchTST —
  one row per walk-forward step, fully tagged, plus a `weights_ref`
  pointer field.
- **Layer 2 — precomputed common keys**: session + subsession + timeframe
  combinations precomputed after each run, each carrying `n`, directional
  accuracy, RMSE, MAE.
- **Layer 3 — on-demand query service**: same shared service as every
  other angle.
- **Weights artifact store**: same pattern as DLinear/LSTM/LPatchTST.

Reuses the exact same 3-layer tagging architecture and weights-artifact
pattern already defined for DLinear/LSTM/LPatchTST — no new storage
design needed for this angle.

## 6) What we will achieve / how to use it

- **The actual point of this angle**: a same-data, same-window,
  same-training-recipe comparison against LPatchTST that directly answers
  "does bolting an LSTM branch onto the patch encoder actually help," on
  our own Alpaca data rather than just trusting the source paper's
  reported numbers.
- A real, backtested directional-accuracy/RMSE number checked against the
  verified 54.1% paper benchmark (this one didn't need correction, unlike
  LSTM/LPatchTST).
- Every trained step's weights kept and referenceable, same as the other
  trained-from-scratch angles.
- Not expected to be independently useful as a standalone signal —
  that's an accepted, stated limitation of this angle, not an oversight.

## 7) Deeper rationale

**Why implement a mediocre model at all:** the honest answer is this
angle isn't being built because plain PatchTST is expected to perform
well — the source paper already says it's barely above passive. It's
built because LPatchTST's own design already promised a comparison that
requires this exact backtest to exist as its counterpart. Skipping this
angle would leave that comparison as an untestable claim instead of a
measured one.

**Why keep the same config as LPatchTST instead of independently tuning
PatchTST's own hyperparameters:** the entire value of this angle is the
controlled comparison — lookback, patch config, training recipe, seed,
and timeframes are all held identical to LPatchTST specifically so any
difference in results can be attributed to the LSTM branch's presence or
absence, not to incidental configuration differences between the two
backtests.

**Why directional accuracy + RMSE/MAE instead of anything else:**
identical reasoning to DLinear/LSTM/LPatchTST — point forecast + no
confidence interval, so direction match is the natural hit definition,
with RMSE/MAE for the "how close in dollars" answer.

**Why N=100 instead of the code's current 90:** same consistency
reasoning as every other raised-floor angle.

**Open/unresolved:** none specific to this angle beyond what's already
flagged for LPatchTST — the corrected/verified benchmark figures come
from a single paper's own asset universe (futures, not equities), so
they're a reference point, not a guarantee of what this backtest
measures on Alpaca data.
