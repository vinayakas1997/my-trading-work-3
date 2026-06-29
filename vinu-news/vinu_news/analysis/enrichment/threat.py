"""Threat classification pattern matrix (Fincept Section 6H)."""

from typing import TypedDict


class ThreatResult(TypedDict):
    threat_level: str
    threat_cat: str
    threat_conf: float


# Ordered list: Critical -> High -> Medium; first match wins
THREAT_PATTERNS: list[tuple[str, str, str, float]] = [
    # Critical
    ("nuclear strike", "conflict", "CRITICAL", 0.95),
    ("nuclear attack", "conflict", "CRITICAL", 0.95),
    ("war declared", "conflict", "CRITICAL", 0.95),
    ("market crash", "market", "CRITICAL", 0.90),
    ("flash crash", "market", "CRITICAL", 0.90),
    ("circuit breaker", "market", "CRITICAL", 0.85),
    ("trading halt", "market", "CRITICAL", 0.85),
    ("bank run", "market", "CRITICAL", 0.90),
    ("sovereign default", "market", "CRITICAL", 0.90),
    # High
    ("cyberattack", "cyber", "HIGH", 0.80),
    ("ransomware", "cyber", "HIGH", 0.80),
    ("data breach", "cyber", "HIGH", 0.75),
    ("invasion", "conflict", "HIGH", 0.85),
    ("airstrike", "conflict", "HIGH", 0.85),
    ("missile launch", "conflict", "HIGH", 0.85),
    ("military deploy", "conflict", "HIGH", 0.80),
    ("coup attempt", "conflict", "HIGH", 0.85),
    ("martial law", "conflict", "HIGH", 0.85),
    ("bankruptcy fil", "market", "HIGH", 0.80),
    ("rate hike", "market", "HIGH", 0.70),
    ("rate cut", "market", "HIGH", 0.70),
    ("earnings miss", "market", "HIGH", 0.75),
    ("profit warning", "market", "HIGH", 0.75),
    ("downgrad", "market", "HIGH", 0.70),
    ("sanction", "regulatory", "HIGH", 0.70),
    ("embargo", "regulatory", "HIGH", 0.75),
    ("earthquake", "natural", "HIGH", 0.80),
    ("tsunami", "natural", "HIGH", 0.85),
    ("hurricane", "natural", "HIGH", 0.75),
    ("pandemic", "natural", "HIGH", 0.80),
    # Medium
    ("protest", "conflict", "MEDIUM", 0.60),
    ("riot", "conflict", "MEDIUM", 0.70),
    ("tension", "conflict", "MEDIUM", 0.50),
    ("escalat", "conflict", "MEDIUM", 0.65),
    ("tariff", "regulatory", "MEDIUM", 0.65),
    ("regulation", "regulatory", "MEDIUM", 0.50),
    ("antitrust", "regulatory", "MEDIUM", 0.60),
    ("investigat", "regulatory", "MEDIUM", 0.55),
    ("layoff", "market", "MEDIUM", 0.60),
    ("recession", "market", "MEDIUM", 0.65),
    ("inflation", "market", "MEDIUM", 0.55),
    ("selloff", "market", "MEDIUM", 0.60),
    ("sell-off", "market", "MEDIUM", 0.60),
    ("volatil", "market", "MEDIUM", 0.50),
    ("wildfire", "natural", "MEDIUM", 0.60),
    ("flood", "natural", "MEDIUM", 0.60),
]

BEARISH_FALLBACK: ThreatResult = {
    "threat_level": "LOW",
    "threat_cat": "general",
    "threat_conf": 0.40,
}

INFO_FALLBACK: ThreatResult = {
    "threat_level": "INFO",
    "threat_cat": "general",
    "threat_conf": 0.30,
}


def classify_threat(combined_text: str, sentiment: str) -> ThreatResult:
    """Match threat patterns in priority order; fallback on sentiment."""
    lower = combined_text.lower()
    for keyword, category, level, confidence in THREAT_PATTERNS:
        if keyword in lower:
            return {
                "threat_level": level,
                "threat_cat": category,
                "threat_conf": confidence,
            }
    if sentiment == "BEARISH":
        return dict(BEARISH_FALLBACK)
    return dict(INFO_FALLBACK)
