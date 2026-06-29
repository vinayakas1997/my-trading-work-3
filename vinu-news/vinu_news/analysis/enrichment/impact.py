"""Impact rating from priority and sentiment strength (Fincept Section 6E)."""

HIGH_PRIORITY = frozenset({"FLASH", "URGENT"})
MEDIUM_PRIORITY = frozenset({"BREAKING"})
HIGH_SENTIMENT_THRESHOLD = 6
MEDIUM_SENTIMENT_THRESHOLD = 3


def classify_impact(priority: str, sentiment_score: int) -> str:
    """Derive impact level from priority and absolute sentiment score."""
    strength = abs(sentiment_score)

    if priority in HIGH_PRIORITY or strength >= HIGH_SENTIMENT_THRESHOLD:
        return "HIGH"
    if priority in MEDIUM_PRIORITY or strength >= MEDIUM_SENTIMENT_THRESHOLD:
        return "MEDIUM"
    return "LOW"
