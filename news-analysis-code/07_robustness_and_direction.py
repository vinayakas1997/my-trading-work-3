"""Two follow-ups the earlier model left open:

1. ROBUSTNESS — the 05 model's 7-8x lift came from ONE chronological
   split (70/30). One split could be a lucky cut. This reruns the same
   model at three different cutoffs (60/40, 70/30, 80/20) so we can see
   whether the lift is stable or was luck.

2. DIRECTION — 05 only ever predicted "will this be a significant event"
   (magnitude/surprise). It said nothing about which way price moves.
   A signal that flags big moves but can't say up-or-down is not
   tradeable. This restricts to the already-significant events and
   checks whether sentiment_score (or anything else) predicts the SIGN
   of the reaction. Sample size here is small by construction (only
   ~88-115 significant events exist per ticker total) — treated
   honestly as a weak/indicative test, not a strong one.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import pointbiserialr
from sklearn.metrics import roc_auc_score
from xgboost import XGBClassifier

from common import TICKERS, compute_novelty, load_article_meta, load_impact_events

FEATURES_NUMERIC = ["sentiment_score", "novelty_score", "ticker_count"]
FEATURES_CATEGORICAL = ["category", "priority", "impact_label", "session", "is_primary"]


def build_dataset(symbol: str) -> pd.DataFrame:
    events = load_impact_events(symbol)
    if events.empty:
        return pd.DataFrame()
    events = compute_novelty(events)
    meta = load_article_meta(events["article_id"].astype(str).tolist())
    merged = events.merge(meta, left_on="article_id", right_on="id", how="left")
    return merged.sort_values("ts").reset_index(drop=True)


def robustness_check(df: pd.DataFrame, symbol: str) -> None:
    df = df.dropna(subset=FEATURES_NUMERIC + ["ar_significant"])
    X = pd.get_dummies(df[FEATURES_NUMERIC + FEATURES_CATEGORICAL], columns=FEATURES_CATEGORICAL, dummy_na=True)
    y = df["ar_significant"].astype(int)

    print(f"\n=== {symbol}: robustness across 3 chronological splits ===")
    for frac in (0.6, 0.7, 0.8):
        split = int(len(df) * frac)
        X_train, X_test = X.iloc[:split], X.iloc[split:]
        y_train, y_test = y.iloc[:split], y.iloc[split:]
        if y_test.sum() < 3 or y_train.sum() < 10:
            print(f"  split={frac}: skipped, too few positives (train={y_train.sum()}, test={y_test.sum()})")
            continue
        model = XGBClassifier(
            n_estimators=200, max_depth=3, learning_rate=0.05, eval_metric="aucpr",
            scale_pos_weight=(len(y_train) - y_train.sum()) / max(y_train.sum(), 1),
        )
        model.fit(X_train, y_train)
        proba = model.predict_proba(X_test)[:, 1]
        auc = roc_auc_score(y_test, proba)
        base_rate = y_test.mean()
        top_n = max(int(len(proba) * 0.1), 1)
        top_idx = np.argsort(proba)[-top_n:]
        top_hit = y_test.iloc[top_idx].mean()
        lift = top_hit / max(base_rate, 1e-9)
        print(f"  split={int(frac*100)}/{int((1-frac)*100)}  test_n={len(y_test)} ({y_test.sum()} positive)  "
              f"AUC={auc:.3f}  top-10% lift={lift:.1f}x")


def direction_check(df: pd.DataFrame, symbol: str) -> None:
    sig = df[df["ar_significant"] == True].dropna(subset=["car_1h"])  # noqa: E712
    sig = sig[sig["car_1h"] != 0]
    print(f"\n=== {symbol}: direction test on {len(sig)} significant events ===")
    if len(sig) < 10:
        print("  too few significant events to test direction reliably — skipped")
        return

    up = (sig["car_1h"] > 0).sum()
    down = (sig["car_1h"] < 0).sum()
    print(f"  of the significant events: {up} moved UP, {down} moved DOWN (base rate: {100*up/len(sig):.1f}% up)")

    direction = (sig["car_1h"] > 0).astype(int)
    for feat in ["sentiment_score", "novelty_score"]:
        vals = sig[feat].dropna()
        common_idx = vals.index.intersection(direction.index)
        if len(common_idx) < 10:
            continue
        r, p = pointbiserialr(direction.loc[common_idx], vals.loc[common_idx])
        flag = "  <-- significant" if p < 0.05 else ""
        print(f"  does {feat} predict direction?  r={r:+.3f}  p={p:.3f}  n={len(common_idx)}{flag}")

    # does the SIGN of sentiment_score at least agree with the sign of
    # the actual reaction more than half the time? simplest possible
    # tradeable check: if sentiment says bullish, did price actually go up?
    agree = ((sig["sentiment_score"] > 0) & (sig["car_1h"] > 0)) | ((sig["sentiment_score"] < 0) & (sig["car_1h"] < 0))
    nonzero_sent = sig[sig["sentiment_score"] != 0]
    if len(nonzero_sent) >= 5:
        agree_rate = agree.loc[nonzero_sent.index].mean()
        print(f"  sentiment-sign-agrees-with-price-direction rate: {100*agree_rate:.1f}% (n={len(nonzero_sent)}, "
              f"50% = coin flip)")


def main() -> None:
    for symbol in TICKERS:
        df = build_dataset(symbol)
        if df.empty or df["ar_significant"].sum() < 10:
            print(f"\n{symbol}: skipped everywhere, too few positive examples")
            continue
        robustness_check(df, symbol)
        direction_check(df, symbol)


if __name__ == "__main__":
    main()
