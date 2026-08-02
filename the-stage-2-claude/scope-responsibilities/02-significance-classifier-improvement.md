---
name: significance-classifier-improvement
component: vinu-initial-analysis
status: not-started
---

# Item 2 — Significance Classifier Coverage Improvement

## What exists right now (built 2026-08-02, already in production)

`vinu_initial_analysis/angles/news_price_causality/significance_model.py`
— trains an XGBoost classifier per run, per symbol, chronological 70/30
split, predicting `ar_significant` (whether an article causes a
statistically significant abnormal price move) from pre-event-only
features: `sentiment_score`, `finbert_score`, `novelty_score`,
`ticker_count`, `category`, `priority`, `session`, `is_primary`. **Read
this file's module docstring in full before changing anything** — it
documents the leakage lesson (original research included `impact_label`,
derived from the same post-event price window as the target, inflating
the reported lift) and the train/test sample-labeling convention
(`significance_score_sample`).

Verified results as of 2026-08-02 (see conversation history / commit
history around this date for the exact re-run):

| Ticker | AUC | Top-decile lift | n_train_positive | n_test_positive |
|---|---|---|---|---|
| AAPL | 0.852 | 5.0x | 161 | 62 |
| TSLA | 0.915 | 6.2x | 143 | 66 |
| JNJ | 0.661 | 6.0x | 15 | 5 |

## The actual gap

JNJ's AUC (0.661) is meaningfully weaker than AAPL/TSLA's (0.85-0.92),
and its train/test positive counts (15/5) are small enough that this
number is not very stable — a couple of different events landing on
either side of the chronological split could move it substantially. This
is very likely a **sample size problem** (JNJ has ~1,500 total articles
vs AAPL's ~17,000 and TSLA's ~21,000 in the same date range — JNJ is a
much lower-news-volume ticker), not a feature-quality problem. Confirm
this diagnosis before trying to fix it as if it were something else.

## Two directions to improve this — evaluate both, don't assume which works

1. **More history for JNJ specifically.** Check whether the Alpaca news
   feed has any earlier JNJ coverage before the current from_ts (currently
   2022-01-01, per the locked Stage 1 window in
   `e2e-test-0731/full-plan.md`) that could extend the training set
   without changing the evaluation window's meaning. Low effort, high
   uncertainty (may simply not exist).

2. **Additional pre-event features from angles already computed.** The
   feature set currently only pulls from the article/event itself. Angles
   like `regime_analysis` (bull/bear/high_vol/sideways classification,
   `vinu_initial_analysis/angles/regime_analysis/compute.py`) and
   `shock_personality` (post-shock behavioral stats) are already computed
   historically for every symbol and could be joined in as additional
   features — e.g. "is the market currently in a high-vol regime when
   this article published" is knowable at publication time (regime is
   classified from price data up to and including the event, not
   requiring the post-event window) and might explain some of the
   variance the current feature set misses. **Before adding any such
   feature, apply the same leakage test used for `impact_label`:** is the
   regime classification for the exact bar the article published on
   computed using ONLY data up to that bar, or does the regime label get
   assigned using a window that extends past the event? Check
   `regime_analysis/compute.py`'s classification logic
   (`classify_regime`, referenced around line 56) before trusting it as
   leak-free.

## Files to touch

- `vinu-components/vinu-initial-analysis/vinu_initial_analysis/angles/news_price_causality/significance_model.py` — extend `FEATURES_NUMERIC`/`FEATURES_CATEGORICAL` if adding regime/shock-personality features; the `score_significance()` function signature would need `articles_by_id` extended or a new `regime_by_symbol`-style lookup passed in.
- `vinu-components/vinu-initial-analysis/vinu_initial_analysis/angles/news_price_causality/compute.py` — the call site (`score_significance(impact_rows, articles_by_id)`, in the `if time_format == "1min"` block) would need to also fetch/pass whatever new feature source is added.
- Reference: `vinu_initial_analysis/angles/regime_analysis/compute.py`, `vinu_initial_analysis/angles/shock_personality/compute.py` — read these fully to understand their output shape and exact computation window before joining anything in.

## Expected output / how to verify

- Re-run `news_price_causality` for AAPL/TSLA/JNJ after any feature
  change (sequentially — see `full-plan.md`'s verification rule) and
  compare the new `significance_model_eval` row's `auc`/`top_decile_lift`
  against the baseline table above, per ticker.
- **A real improvement means JNJ's AUC moves meaningfully above 0.661
  without AAPL/TSLA's AUC dropping.** If JNJ improves but AAPL/TSLA get
  worse, the new feature is probably overfitting or diluting signal that
  matters more for the higher-volume tickers — don't ship that trade
  blindly, report it as a real finding either way (matches this
  project's established norm of reporting negative results honestly, not
  just wins).
- If neither direction (more JNJ history, more features) moves the
  needle, that's a legitimate, reportable outcome — "JNJ's classifier is
  weak because JNJ generates too little news, full stop" is an honest
  conclusion, not a failure to hide.
