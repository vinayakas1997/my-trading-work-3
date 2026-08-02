"""Predicts whether a news article will cause a statistically significant
abnormal price move — BEFORE the price move has happened.

WHAT THIS IS FOR AND HOW TO USE IT (read this before touching it):
  `ar_significant` (computed in impact.py / _helpers.py) tells you whether
  a move WAS significant, but only after the fact — it needs price_change_*
  and the abnormal-return event window (30-60 min post-article) to exist.
  That's useless for anything that wants to act when the article lands.

  `significance_score` is this module's output: a predicted PROBABILITY
  (0-1) that ar_significant will end up True, estimated using ONLY
  features that are known the instant the article is published:
  sentiment_score, finbert_score, novelty_score, category, priority,
  session, is_primary, ticker_count. It deliberately does NOT use
  impact_label or any price_change_* field — those are derived from the
  same post-event price window as ar_significant itself, so including
  them would leak the answer into the "prediction" and inflate the
  reported accuracy without producing anything usable in real time (this
  was caught and removed during integration — see git history on this
  file; the original research script 05_multivariate_model.py had this
  leak and its 7-8x lift number was partly inflated by it).

  Practical use: sort articles by significance_score to prioritize which
  ones are worth a human/downstream-system's attention before the price
  data confirms it either way. Do NOT treat this as a trading signal on
  its own — it predicts MAGNITUDE/surprise, not DIRECTION (see
  news-analysis-code/07_robustness_and_direction.py and
  08_finbert_direction.py: neither the old rule-based sentiment nor
  FinBERT sentiment predicts the sign of the reaction above a coin flip,
  even on already-significant events).

TRUST BUT VERIFY: a fresh model is trained per run on THIS run's own
  history via a chronological 70/30 split (never random — shuffling
  time-series data leaks future information into training). Every row
  gets scored, but only the last 30% (chronologically) is genuinely
  held-out / trustworthy; the first 70% is in-sample and will look
  optimistically good — check `significance_score_sample` per row
  ("train" vs "test") before drawing conclusions from any specific score.
  The honest accuracy number for THIS run is stored as one row of type
  "significance_model_eval" in the same output (auc, top_decile_lift,
  base_rate, n_train, n_test) — read that row before trusting the scores
  on a symbol you haven't checked before. If a symbol has too little
  history or too few significant events to train reliably, no scores or
  eval row are produced at all (silently — check for the eval row's
  absence, not for a placeholder value).
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

LOG = logging.getLogger(__name__)

FEATURES_NUMERIC = ["sentiment_score", "finbert_score", "novelty_score", "ticker_count"]
FEATURES_CATEGORICAL = ["category", "priority", "session", "is_primary"]

MIN_TRAIN_POSITIVES = 10
MIN_TEST_POSITIVES = 3
TRAIN_FRACTION = 0.7


def score_significance(
    impact_rows: list[dict],
    articles_by_id: dict[str, dict[str, Any]],
) -> tuple[dict[int, float], dict[int, str], dict[str, Any] | None]:
    """Train + score in one pass over this run's impact rows.

    Returns (scores, sample_labels, eval_metrics):
      scores        {row_index_in_impact_rows: significance_score}
      sample_labels {row_index_in_impact_rows: "train" | "test"}
      eval_metrics  dict for a "significance_model_eval" summary row, or
                    None if there wasn't enough data to train at all.
    Row indices are positions into `impact_rows`, so callers zip scores
    back onto the same list they passed in.
    """
    if not impact_rows:
        return {}, {}, None

    df = pd.DataFrame(impact_rows)
    df["_orig_idx"] = range(len(df))
    df["finbert_score"] = df["article_id"].map(
        lambda aid: articles_by_id.get(aid, {}).get("finbert_score")
    )
    df["category"] = df["article_id"].map(
        lambda aid: articles_by_id.get(aid, {}).get("category")
    )
    df["priority"] = df["article_id"].map(
        lambda aid: articles_by_id.get(aid, {}).get("priority")
    )

    df = df.sort_values("ts").reset_index(drop=True)
    usable = df.dropna(subset=FEATURES_NUMERIC + ["ar_significant"])
    if len(usable) < (MIN_TRAIN_POSITIVES + MIN_TEST_POSITIVES) * 10:
        LOG.info("Not enough rows with complete features to train significance model (%d)", len(usable))
        return {}, {}, None

    X = pd.get_dummies(usable[FEATURES_NUMERIC + FEATURES_CATEGORICAL], columns=FEATURES_CATEGORICAL, dummy_na=True)
    y = usable["ar_significant"].astype(int)

    split = int(len(usable) * TRAIN_FRACTION)
    y_train, y_test = y.iloc[:split], y.iloc[split:]
    if y_train.sum() < MIN_TRAIN_POSITIVES or y_test.sum() < MIN_TEST_POSITIVES:
        LOG.info(
            "Not enough positive examples to train/eval significance model (train=%d, test=%d)",
            y_train.sum(), y_test.sum(),
        )
        return {}, {}, None

    from xgboost import XGBClassifier
    from sklearn.metrics import roc_auc_score, average_precision_score

    X_train, X_test = X.iloc[:split], X.iloc[split:]
    model = XGBClassifier(
        n_estimators=200, max_depth=3, learning_rate=0.05, eval_metric="aucpr",
        scale_pos_weight=(len(y_train) - y_train.sum()) / max(y_train.sum(), 1),
    )
    model.fit(X_train, y_train)

    proba_all = model.predict_proba(X)[:, 1]
    proba_test = model.predict_proba(X_test)[:, 1]

    auc = float(roc_auc_score(y_test, proba_test))
    avg_precision = float(average_precision_score(y_test, proba_test))
    base_rate = float(y_test.mean())
    top_n = max(int(len(proba_test) * 0.1), 1)
    top_idx = np.argsort(proba_test)[-top_n:]
    top_decile_lift = float(y_test.iloc[top_idx].mean() / max(base_rate, 1e-9))

    orig_idx = usable["_orig_idx"].to_numpy()
    scores = {int(orig_idx[i]): float(proba_all[i]) for i in range(len(orig_idx))}
    sample_labels = {
        int(orig_idx[i]): ("train" if i < split else "test")
        for i in range(len(orig_idx))
    }
    eval_metrics = {
        "n_train": int(len(X_train)),
        "n_test": int(len(X_test)),
        "n_train_positive": int(y_train.sum()),
        "n_test_positive": int(y_test.sum()),
        "base_rate": round(base_rate, 6),
        "auc": round(auc, 4),
        "avg_precision": round(avg_precision, 4),
        "top_decile_lift": round(top_decile_lift, 2),
    }
    return scores, sample_labels, eval_metrics
