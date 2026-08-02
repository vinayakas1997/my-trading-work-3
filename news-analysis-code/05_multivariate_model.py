"""Technique 5: multivariate model — combine every feature at once.

Everything so far (01-04) tested ONE feature at a time against
ar_significant: category alone, priority alone, sentiment alone, novelty
alone. That's the weak version. Real quant research (gradient-boosted
models are specifically called out as the strongest performer for this
exact classification task — see sources in the reply) combines features
into one model, because the real signal is often an INTERACTION that no
single-variable test can see: e.g. "novel AND high-sentiment AND
EARNINGS category" might be a strong combined signal even if none of
those three show anything alone.

This trains a gradient-boosted classifier to predict ar_significant from:
  sentiment_score, novelty_score, category, priority, impact_label,
  is_primary, ticker_count, session

Two things this script does that the univariate scripts didn't, because
they matter a lot for trusting the result:
  1. CHRONOLOGICAL train/test split, not random. Randomly shuffling time-
     series data leaks future information into training (an article's
     novelty_score already depends on what happened right after it in a
     random split) and would silently inflate the score.
  2. AUC / precision-recall, not accuracy. ar_significant is ~0.5-0.7%
     positive. A model that always predicts "no" gets ~99.4% accuracy
     and is worthless — AUC and precision-at-threshold are the only
     honest way to judge this.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score
from xgboost import XGBClassifier

from common import TICKERS, compute_novelty, load_article_meta, load_impact_events

FEATURES_NUMERIC = ["sentiment_score", "novelty_score", "ticker_count"]
FEATURES_CATEGORICAL = ["category", "priority", "impact_label", "session", "is_primary"]


def build_dataset(symbol: str) -> pd.DataFrame:
    events = load_impact_events(symbol)
    if events.empty:
        return pd.DataFrame()
    events = compute_novelty(events)  # adds novelty_score, needs headline+ts (already sorted by this)

    meta = load_article_meta(events["article_id"].astype(str).tolist())
    merged = events.merge(meta, left_on="article_id", right_on="id", how="left")
    return merged.sort_values("ts").reset_index(drop=True)


def main() -> None:
    for symbol in TICKERS:
        df = build_dataset(symbol)
        if df.empty or df["ar_significant"].sum() < 10:
            print(f"{symbol}: not enough positive examples to train on ({df['ar_significant'].sum() if not df.empty else 0})")
            continue

        df = df.dropna(subset=FEATURES_NUMERIC + ["ar_significant"])
        X = pd.get_dummies(df[FEATURES_NUMERIC + FEATURES_CATEGORICAL], columns=FEATURES_CATEGORICAL, dummy_na=True)
        y = df["ar_significant"].astype(int)

        # chronological split: first 70% trains, last 30% tests — never
        # let the model see the future during training.
        split = int(len(df) * 0.7)
        X_train, X_test = X.iloc[:split], X.iloc[split:]
        y_train, y_test = y.iloc[:split], y.iloc[split:]

        if y_test.sum() < 3:
            print(f"{symbol}: too few positive examples in the test window ({y_test.sum()}) to score reliably")
            continue

        model = XGBClassifier(
            n_estimators=200, max_depth=3, learning_rate=0.05,
            eval_metric="aucpr", scale_pos_weight=(len(y_train) - y_train.sum()) / max(y_train.sum(), 1),
        )
        model.fit(X_train, y_train)
        proba = model.predict_proba(X_test)[:, 1]

        auc = roc_auc_score(y_test, proba)
        ap = average_precision_score(y_test, proba)
        base_rate = y_test.mean()

        print(f"\n=== {symbol} ===")
        print(f"  train n={len(X_train)} ({y_train.sum()} positive)  test n={len(X_test)} ({y_test.sum()} positive)")
        print(f"  base rate in test set: {100*base_rate:.3f}%")
        print(f"  ROC-AUC: {auc:.4f}   (0.5 = no better than random)")
        print(f"  Average Precision: {ap:.4f}   (compare against base rate {base_rate:.4f} — that's the random-guess floor)")

        # top-decile check: if we only acted on the model's top 10% most
        # confident predictions, what fraction are actually significant?
        # this is the practically useful number, not AUC.
        top_n = max(int(len(proba) * 0.1), 1)
        top_idx = np.argsort(proba)[-top_n:]
        top_hit_rate = y_test.iloc[top_idx].mean()
        print(f"  top-10%-confidence hit rate: {100*top_hit_rate:.3f}%  vs base rate {100*base_rate:.3f}%  "
              f"({top_hit_rate/max(base_rate,1e-9):.1f}x lift)")

        importances = pd.Series(model.feature_importances_, index=X.columns).sort_values(ascending=False)
        print("  top 8 features by importance:")
        print("   " + importances.head(8).round(4).to_string().replace("\n", "\n   "))


if __name__ == "__main__":
    main()
