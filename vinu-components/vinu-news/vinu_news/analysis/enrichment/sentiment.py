"""Weighted sentiment scoring with financial domain lexicon (Fincept Section 6D)."""

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

# Financial domain lexicon — multi-word phrases that carry strong sentiment
# in a market context but may be missed or mis-scored by general VADER rules.
FINANCIAL_LEXICON: dict[str, int] = {
    # Earnings / Results — weight +3
    "beat estimates": 3,
    "beat expectations": 3,
    "record profit": 3,
    "record revenue": 3,
    "strong earnings": 3,
    "raised guidance": 3,
    "upgraded to buy": 3,
    "outperform rating": 2,
    "above consensus": 2,
    "strong quarter": 2,
    "gross margin expansion": 2,
    "earnings surprise": 2,
    "revenue growth": 2,
    "profit beat": 3,
    # Earnings / Results — weight -3
    "miss estimates": -3,
    "miss expectations": -3,
    "missed estimates": -3,
    "missed expectations": -3,
    "lowered guidance": -3,
    "weak earnings": -3,
    "profit warning": -3,
    "revenue miss": -3,
    "earnings miss": -3,
    "below consensus": -2,
    "guidance cut": -3,
    "downgraded to sell": -3,
    "sell rating": -1,
    "underperform rating": -2,
    # Regulatory / Legal — weight -3
    "sec investigation": -3,
    "sec probe": -3,
    "doj investigation": -3,
    "antitrust lawsuit": -3,
    "class action": -3,
    "regulatory probe": -3,
    "consent decree": -2,
    "subpoena": -2,
    "whistleblower": -2,
    "penalty": -2,
    "fine": -2,
    "sanctions": -2,
    # M&A / Corporate actions
    "merger": 1,
    "acquisition": 1,
    "buyback": 2,
    "share buyback": 2,
    "stock split": 1,
    "dividend increase": 2,
    "dividend cut": -2,
    "ipo": 1,
    "spin off": 1,
    # Market sentiment
    "overweight": 1,
    "equal weight": 0,
    "underweight": -1,
    "price target raised": 2,
    "price target lowered": -2,
    "bull case": 2,
    "bear case": -2,
    "bull run": 2,
    "bear market": -2,
    "dead cat bounce": -2,
    "short squeeze": 2,
    "flight to safety": -1,
    "risk on": 1,
    "risk off": -1,
    # Macro / Economy
    "rate hike": -1,
    "rate cut": 2,
    "hawkish": -1,
    "dovish": 1,
    "quantitative easing": 1,
    "quantitative tightening": -1,
    "soft landing": 1,
    "hard landing": -2,
    "inflation cools": 1,
    "inflation spikes": -2,
    "jobs report": 1,
    # Analyst actions
    "double downgrade": -3,
    "triple downgrade": -3,
    "upgraded to overweight": 2,
    "downgraded to underweight": -2,
    "conviction buy": 3,
    "top pick": 2,
    "added to conviction list": 2,
    "removed from conviction list": -1,
    # Supply chain / Operations
    "supply chain disruption": -2,
    "factory shutdown": -2,
    "production halt": -2,
    "recall": -2,
    "inventory glut": -1,
    "surplus": 0,
    # Technology / Industry specific
    "fda approval": 3,
    "fda rejection": -3,
    "clinical trial success": 3,
    "clinical trial failure": -3,
    "patent approval": 2,
    "patent infringement": -2,
    "regulatory approval": 2,
    "regulatory delay": -1,
    # Credit / Debt
    "credit rating upgrade": 2,
    "credit rating downgrade": -2,
    "junk bond": -1,
    "investment grade": 1,
    "default risk": -2,
    "solvency": 1,
    "liquidity crisis": -3,
    "debt restructuring": -1,
    "bank run": -3,
}


def score_sentiment(combined_text: str) -> dict:
    """Cumulative weighted tally with financial domain lexicon; returns sentiment label and net score."""
    lower = combined_text.lower()
    pos = 0
    neg = 0

    # Phase 1: Multi-word financial phrases (longest first to avoid partial matches)
    fin_items = sorted(FINANCIAL_LEXICON.items(), key=lambda x: len(x[0]), reverse=True)
    for phrase, weight in fin_items:
        if phrase in lower:
            if weight > 0:
                pos += weight
            elif weight < 0:
                neg += abs(weight)
            # Replace matched phrase to avoid double-counting individual words
            lower = lower.replace(phrase, " " * len(phrase))

    # Phase 2: Individual sentiment words (longest first)
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
