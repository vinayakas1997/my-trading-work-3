# Angle reference — 28 files, one per real angle

**Every "FAKE example result" JSON block in these 28 files is fabricated
data, invented for prompt-design/testing purposes only — none of it was
sampled from any real angle run, and it must never be treated as a real
signal for any symbol.**

Purpose: ground everything downstream (the glossary blurbs, the cluster
digest design, the checkpoint trials) in the real catalog before writing
any prompt code — per direction, build this first, then the prompts,
then verify, then implement.

Each `NN-<angle_id>.md` file has three parts, all for one real angle
from `vinu-initial-analysis/vinu_initial_analysis/catalog/angles.yaml`:

1. **Real catalog data** — `purpose`, `time_formats`, `inputs`, output
   `description`, copied verbatim from `angles.yaml`, never paraphrased.
2. **A FAKE example result** — clearly labeled synthetic, built to match
   the real output shape (`outputs[].description`) but never sampled
   from any real run. Exists so the cluster-digest/prompt work
   (`01-plan.md` steps 3 and 5) has something concrete to test against
   before a real LLM endpoint or real computed data is available.
3. **A draft condensed glossary blurb** — the actual Step-1 deliverable
   from `../01-plan.md`, capped at ~50 words, shorter for angles built
   on a recognizable published architecture, fuller for proprietary/
   opaque ones.

Cluster assignments (Cluster A-G) match `../00-explanation.md` section 3
exactly — every file states which cluster it belongs to.

| # | Angle id | Title | Cluster |
|---|---|---|---|
| 01 | arima | ARIMA Classical Statistical Baseline | A |
| 02 | backtesting_44_metrics | Backtesting Metrics | G |
| 03 | chronos | Chronos Time-Series Foundation Model | B |
| 04 | dlinear | DLinear Decomposition Linear Forecast | B |
| 05 | drawdown_deep_dive | Drawdown Deep-Dive | C |
| 06 | exponential_smoothing | Exponential Smoothing Classical Baseline | A |
| 07 | garch | GARCH Volatility Forecast | C |
| 08 | itransformer | iTransformer Cross-Variate Attention Forecast | B |
| 09 | kalman_filters | Kalman Filter State Estimation | A |
| 10 | kronos | Kronos Financial K-Line Foundation Model | B |
| 11 | lag_llama | Lag-Llama Probabilistic Time-Series Model | B |
| 12 | lpatchtst | LPatchTST LSTM+PatchTST Hybrid Forecast | B |
| 13 | lstm | LSTM Sequential Forecast | B |
| 14 | moirai | MOIRAI Any-Variate Time-Series Foundation Model | B |
| 15 | moment | MOMENT Multi-Task Time-Series Foundation Model | B |
| 16 | news_price_causality | News-Price Causality | F |
| 17 | patchtst | PatchTST Channel-Independent Patch Transformer | B |
| 18 | peer_relative_strength | Peer Relative Strength | F |
| 19 | pnl_attribution | PnL Attribution | G |
| 20 | regime_analysis | Regime Analysis | D |
| 21 | shock_clustering | Shock Clustering | E |
| 22 | shock_personality | Shock Personality | E |
| 23 | tft | TFT Temporal Fusion Transformer | B |
| 24 | timer_timerxl | Timer / Timer-XL Patch-Based Foundation Model | B |
| 25 | timesfm | TimesFM Time-Series Foundation Model | B |
| 26 | tips_regime_aware_transformer | TIPS Regime-Aware Transformer Forecast | B |
| 27 | trend_lifecycle | Trend Lifecycle | D |
| 28 | trend_session_structure | Trend Session Structure | D |

## Status

All 28 built. Next: use these to actually draft the `cluster_digest`
prompt section (`01-plan.md` step 3/5) and the `angle_glossary.py` data
module (step 1) from the blurbs already drafted in each file — then test
that shape against checkpoint 01 once a real endpoint exists, per the
original instruction ("build the prompt, see that it's working, then
start building").
