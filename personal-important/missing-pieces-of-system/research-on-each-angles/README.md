# Research on each angle

## What this folder is for

One researched, cited explanation file per real `vinu-initial-analysis`
angle (28 total). Each file answers, for one angle: what it is, what it
assumes, what published sources report happens when those assumptions
are set a certain way, and what its real output fields mean.

## Why this exists

A real gap, confirmed against the code (2026-09-24): the explanation an
LLM gets for an angle has no enforced link to the data that angle
actually produces. Example: the glossary
(`vinu-agent/vinu_agent/tools/angle_glossary.py`) tells the model to
"read its `forecast_price`" for `arima` -- but `arima/compute.py` never
emits a field called `forecast_price`; the real field is `forecast`.
Nothing checked the two against each other, so they drifted. Separately,
nothing anywhere records an angle's assumptions or where they come from.

## What each file contains

**Passed downstream to the LLM** (short -- the local model is slow, every
token costs):
- **Short definition** -- plain-language, one or two sentences.
- **Assumptions** -- what the method assumes about the data.
- **Assumption results** -- what published sources report when an
  assumption/parameter is set a particular way ("they set X, the reported
  result was Y"). Researched evidence, not something computed per ticker.
- **Output fields** -- every real field the angle emits and its meaning,
  taken from the angle's own `compute.py`, never from the internet.
- **Status values** -- what `ok` / `no_data` / `insufficient_data` / etc.
  mean, also from the real code.

**For human understanding only** (never sent to the LLM):
- **Citations** -- where each assumption and result came from.
- **Comprehensive explanation** -- the full, granular in-and-out
  explanation.

## Rules

- **Every citation is a source actually opened and read during the
  research**, never one recalled from memory. A fabricated paper or URL
  is worse than no citation.
- **Output fields and status values come from the real code**, with the
  file cited, so they can later be checked automatically against what
  the angle really emits.
- Where the code's own choice differs from what the literature
  recommends, say so plainly -- that's useful, not embarrassing.

## Files

Numbered in the same order as `vinu-initial-analysis/.../catalog/angles.yaml`.

| # | Angle | Cluster | Status |
|---|---|---|---|
| 01 | arima | A | done -- template approved |
| 02 | backtesting_44_metrics | G | done -- 2 real formula bugs found (Sharpe, Sortino) |
| 03 | chronos | B | done -- ~0.73%-of-price resolution limit; faster/more accurate successor exists |
| 04 | dlinear | B | done -- trend padding bug confirmed in container; no naive baseline |
| 05 | drawdown_deep_dive | C | done -- news attribution never matches (confirmed vs. real news service); live path uses fixed -2% |
| 06 | exponential_smoothing | A | done -- no real bug; naming trap (`beta` is a weight, not the trend); no-damping risk is low since forecast is 1-step |
| 07 | garch | C | done -- no live bug (a real prior unit-mixing bug was already found/fixed by the code itself, verified); known simplification: symmetric GARCH misses the leverage effect; unused `egarch_volatility` already exists |
| 08 | itransformer | B | done -- code already admits it doesn't do cross-asset attention; paper's own ablation says cross-variate attention needs many variates, code uses only 5 (OHLCV channels); on the one financial dataset either paper tested, naive ≈ DLinear > iTransformer |
| 09 | kalman_filters | A | done -- confirmed (direct container test) that live `smoothed_*` fields always exactly equal `filtered_*`, redundant under a different name; backtest itself is a careful, correct example (look-ahead bias explicitly avoided) |
| 10 | kronos | B | done -- no live bug; correct checkpoint/tokenizer pairing and correct context-window truncation (verified in vendored code); real gap is untested context adequacy at intraday timeframes vs. the paper's own per-frequency lookbacks |
| 11 | lag_llama | B | done -- always `fallback_proxy` (honestly labeled); real bug found by tracing code: quantile spread anchors to the fixed original close, not the compounding forecast price; Gaussian band mismatches known fat-tailed real returns |
| 12 | lpatchtst | B | done -- architecture-fidelity gap: cited paper's "LSTM+PatchTST" is sequential (LSTM denoises, then PatchTST), code runs both branches in parallel and concatenates; "best-performing" claim is true for Sharpe but not hit rate (tft reportedly higher) |
| 13 | lstm | B | done -- no code bug; flagged an unconfirmed possible stale citation (code's own "~51%" vs. the likely-same survey's real 55.4% for plain LSTM); otherwise solid, mid-pack per the shared benchmark table |
| 14 | moirai | B | done -- always `fallback_proxy` (honestly labeled, sound reasoning verified against the real paper's mechanism); same spread-anchoring bug as `lag_llama`'s fallback, in near-identical code -- looks copy-pasted |
| 15 | moment | B | done -- always `fallback_proxy`; install failure independently corroborated character-for-character (real Python 3.12/pkgutil incompatibility); this fallback's spread-anchor is actually consistent, unlike lag_llama/moirai's |
| 16 | news_price_causality | D | done -- real bug: Granger `p_value` is the min across 12 untested lags (textbook p-hacking per Bruns & Stern 2019), same pattern repeats in lag-correlation selection; otherwise the most methodologically self-aware angle researched (leakage caught, honest negative result reported) |
| 17 | patchtst | B | done -- PatchTST's own authors deliberately excluded financial/exchange-rate data from their benchmark, citing EMH; strongest version yet of this cluster's recurring "no real evidence for finance" pattern; implementation itself is architecturally faithful |
| 18 | peer_relative_strength | E | done -- serious live bug (confirmed by tracing runner.py + compute.py): peers always fetched as real daily bars, but the ticker's own series is fetched at whatever intraday timeframe was requested; the two get joined/ffilled on mismatched timestamp resolutions for all 5 non-1D timeframes |
| 19 | pnl_attribution | G | done -- not a forecaster, push-fed realized-trade stats; `win_rate`'s CI reuses a t-interval meant for continuous values on a binomial proportion, the known-poor-coverage "Wald interval" case (Agresti & Coull 1998); otherwise solid |
| 20 | regime_analysis | C | done -- already fixed one real look-ahead leak (cited from a sibling module); live gap: fixed bar-counted thresholds (20-bar return, 120-bar vol baseline) applied unchanged across 8 declared timeframes spanning minutes to years, so "bull"/"bear" mean different things per timeframe |
| 21 | shock_clustering | C | done -- third instance of the peer/anchor-timeframe-mismatch bug (peers always fetched daily); also two new bugs found: date-keyed dict silently drops all but 1 of ~390 intraday bars/day, and the "gap" trigger is an overnight-only concept broken by intraday bars; module already fixed 2 other real bugs itself before this research |
| 22 | shock_personality | C | done -- most self-corrected angle yet (3 real bugs fixed and documented: leak, computed-then-discarded autocorrelation, computed-then-unreported news tags); fourth instance of the daily-only-constants-across-6-timeframes pattern; one hardcoded time_format confirmed harmless by tracing garch_volatility's source |
| 23 | tft | B | done -- "interpretable multi-head attention" claim doesn't hold (code uses plain nn.MultiheadAttention; paper explicitly requires shared per-head values for interpretability); TFT's one real financial benchmark win is for volatility, not returns; otherwise strongest of the 6 from-scratch architectures per shared benchmark table |
| 24 | timer_timerxl | B | done -- cleanest DL angle researched: two numbers that looked like discrepancies (260B pretraining points, 2880 context) both verified correct against the actual checkpoint's own model card, not the paper; real Timer-XL differentiator (cross-series attention) has zero financial evaluation anyway |
| 25 | timesfm | B | done -- even cleaner than timer_timerxl: max_context, full ForecastConfig (all 7 params), and quantile-output ordering all verified word-for-word against the real model card, no discrepancies found |
| 26 | tips_regime_aware_transformer | B | done -- the strongest architecture-fidelity gap in this folder: real TIPS (arXiv:2603.16985) is a 7-teacher knowledge-distillation framework with emergent, non-explicit regime behavior; code implements an unrelated hand-built 2-head autocorrelation-gated model; real paper's substantial SP500 results don't transfer |
| 27 | trend_lifecycle | F | done -- real bug: peak-drop threshold table missing 1min/5min entries, silently falls back to the 1H value (-3%); the ATR floor next to it can only tighten the threshold, never loosen it, so it doesn't compensate; walk-forward-safe matching design is genuinely careful |
| 28 | trend_session_structure | F | done -- ALL 28 ANGLES COMPLETE. Real bug: `_INTRADAY_FORMATS` excludes 1min/5min despite spec.yaml declaring them; compounds with angle 27's own 1min/5min gap one layer upstream -- fixing either alone wouldn't be enough |
