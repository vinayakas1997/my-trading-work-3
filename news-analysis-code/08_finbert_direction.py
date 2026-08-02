"""Does FinBERT sentiment predict direction any better than the old
rule-based sentiment_score did?

07_robustness_and_direction.py already established that sentiment_score
(the crude rule-based score) does NOT reliably predict the sign of the
price reaction on already-significant events. FinBERT was added to
vinu-news specifically to replace that crude scorer with a real NLP
sentiment model — this checks whether it actually moves the needle on
the one thing that mattered: predicting UP vs DOWN, not just polarity.

Same honesty rules as 07: small sample by construction (only events
already flagged ar_significant), reported as an indicative test, not
a strong one. Compares finbert_score head-to-head against sentiment_score
on the identical event set so the two are directly comparable.
"""

from __future__ import annotations

from scipy.stats import pointbiserialr

from common import TICKERS, load_article_meta, load_impact_events


def direction_check(symbol: str) -> None:
    events = load_impact_events(symbol)
    if events.empty:
        print(f"\n{symbol}: no impact events, skipped")
        return

    meta = load_article_meta(events["article_id"].astype(str).tolist())
    df = events.merge(meta, left_on="article_id", right_on="id", how="left")

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

    for feat, label in [("sentiment_score", "rule-based sentiment_score (old)"), ("finbert_score", "FinBERT finbert_score (new)")]:
        if feat not in sig.columns:
            print(f"  {label}: column missing, skipped")
            continue
        vals = sig[feat].dropna()
        common_idx = vals.index.intersection(direction.index)
        if len(common_idx) < 10:
            print(f"  {label}: only {len(common_idx)} non-null values, skipped")
            continue
        r, p = pointbiserialr(direction.loc[common_idx], vals.loc[common_idx])
        flag = "  <-- significant" if p < 0.05 else ""
        print(f"  does {label} predict direction?  r={r:+.3f}  p={p:.3f}  n={len(common_idx)}{flag}")

        # tradeable check: does the sign of the score at least agree with
        # the sign of the actual reaction more than half the time?
        nonzero = sig.loc[common_idx]
        nonzero = nonzero[nonzero[feat] != 0]
        if len(nonzero) >= 5:
            agree = ((nonzero[feat] > 0) & (nonzero["car_1h"] > 0)) | ((nonzero[feat] < 0) & (nonzero["car_1h"] < 0))
            print(f"    sign-agrees-with-price-direction rate: {100*agree.mean():.1f}% (n={len(nonzero)}, 50% = coin flip)")

    # does FinBERT's own 3-way label (positive/negative/neutral) do any
    # better than the continuous score, e.g. because it discards the
    # neutral middle where the score is noisiest?
    if "finbert_label" in sig.columns:
        directional = sig[sig["finbert_label"].isin(["positive", "negative"])]
        if len(directional) >= 5:
            agree = ((directional["finbert_label"] == "positive") & (directional["car_1h"] > 0)) | \
                    ((directional["finbert_label"] == "negative") & (directional["car_1h"] < 0))
            print(f"  FinBERT label (pos/neg only, neutral excluded) agrees with direction: "
                  f"{100*agree.mean():.1f}% (n={len(directional)}, 50% = coin flip)")


def main() -> None:
    for symbol in TICKERS:
        direction_check(symbol)


if __name__ == "__main__":
    main()
