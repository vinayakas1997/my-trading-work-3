"""Priority classification waterfall (Fincept Section 6C)."""

PRIORITY_LEVELS = [
    ("FLASH", ("breaking", "alert")),
    ("URGENT", ("urgent", "emergency")),
    ("BREAKING", ("announce", "report")),
]


def classify_priority(combined_text: str) -> str:
    """Classify priority using strict waterfall precedence."""
    lower = combined_text.lower()
    for level, keywords in PRIORITY_LEVELS:
        if any(kw in lower for kw in keywords):
            return level
    return "ROUTINE"
