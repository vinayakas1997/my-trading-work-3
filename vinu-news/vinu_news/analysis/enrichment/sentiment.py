"""Weighted sentiment scoring (Fincept Section 6D)."""

POSITIVE_WORDS = {
    # Weight +3
    "surge": 3,
    "soar": 3,
    "skyrocket": 3,
    "breakthrough": 3,
    "boom": 3,
    "record high": 3,
    # Weight +2
    "rally": 2,
    "gain": 2,
    "rise": 2,
    "jump": 2,
    "climb": 2,
    "spike": 2,
    "rebound": 2,
    "boost": 2,
    "beat": 2,
    "exceed": 2,
    "upgrade": 2,
    "profit": 2,
    "growth": 2,
    "expand": 2,
    "recover": 2,
    "victory": 2,
    "ceasefire": 2,
    "treaty": 2,
    "reform": 2,
    "optimism": 2,
    "milestone": 2,
    # Weight +1
    "strong": 1,
    "robust": 1,
    "stellar": 1,
    "buy": 1,
    "positive": 1,
    "success": 1,
    "win": 1,
    "approval": 1,
    "deal": 1,
    "confidence": 1,
    "dividend": 1,
    "progress": 1,
    "improve": 1,
    "hope": 1,
    "support": 1,
    "bolster": 1,
    "outperform": 1,
    "bullish": 1,
    "upside": 1,
    "favorable": 1,
    "momentum": 1,
    "launch": 1,
    "unveil": 1,
}

NEGATIVE_WORDS = {
    # Weight -3
    "crash": -3,
    "plunge": -3,
    "collapse": -3,
    "devastat": -3,
    "catastroph": -3,
    "invasion": -3,
    "war crime": -3,
    "nuclear": -3,
    "bankruptcy": -3,
    "meltdown": -3,
    # Weight -2
    "fall": -2,
    "drop": -2,
    "decline": -2,
    "tumble": -2,
    "slide": -2,
    "slump": -2,
    "miss": -2,
    "disappoint": -2,
    "fail": -2,
    "recession": -2,
    "crisis": -2,
    "conflict": -2,
    "attack": -2,
    "kill": -2,
    "sanction": -2,
    "tariff": -2,
    "escalat": -2,
    "layoff": -2,
    "downgrade": -2,
    "default": -2,
    "fraud": -2,
    "scandal": -2,
    "coup": -2,
    "protest": -2,
    "disaster": -2,
    # Weight -1
    "worst": -1,
    "weak": -1,
    "loss": -1,
    "deficit": -1,
    "fear": -1,
    "risk": -1,
    "threat": -1,
    "warning": -1,
    "sell": -1,
    "debt": -1,
    "inflation": -1,
    "slowdown": -1,
    "bearish": -1,
    "negative": -1,
    "volatile": -1,
    "uncertain": -1,
    "reject": -1,
    "ban": -1,
    "suspend": -1,
    "investigat": -1,
    "probe": -1,
    "hack": -1,
    "leak": -1,
    "shortage": -1,
    "disrupt": -1,
    "shrink": -1,
}


def score_sentiment(combined_text: str) -> dict:
    """Cumulative weighted tally; returns sentiment label and net score."""
    lower = combined_text.lower()
    pos = 0
    neg = 0

    # Longer phrases first to avoid partial double-counting on multi-word entries
    all_words = sorted(
        {**POSITIVE_WORDS, **NEGATIVE_WORDS}.items(),
        key=lambda x: len(x[0]),
        reverse=True,
    )
    for word, weight in all_words:
        if word in lower:
            if weight > 0:
                pos += weight
            else:
                neg += abs(weight)

    net = pos - neg
    if net >= 1:
        label = "BULLISH"
    elif net <= -1:
        label = "BEARISH"
    else:
        label = "NEUTRAL"

    return {
        "sentiment": label,
        "sentiment_score": net,
        "positive_total": pos,
        "negative_total": neg,
    }
