"""Method 1 — Event-Type Classification.

Spec: New-talk-/Final-implementation/01-present-considerations/01-event-type-classification.md

Build call: **adapt**. The spec's Option 1 (the only path that survives
the project's no-LLM limitation) is literally "extend
`vinu_news/analysis/enrichment/category.py`'s `CATEGORY_KEYWORDS`
waterfall with finer sub-categories". `category.py`'s existing
`CATEGORY_KEYWORDS` is sector-level (EARNINGS, CRYPTO, ECONOMIC, ...),
not fine-grained event-level (EARNINGS_BEAT vs EARNINGS_MISS vs
GUIDANCE_CUT vs GUIDANCE_RAISE), so there's no existing table to literally
extend without breaking `category.py`'s own behavior/tests. This module
reuses `category.py`'s exact mechanism (ordered keyword waterfall, first
match wins, plain substring match on lowercased text) with a new,
finer-grained keyword table, matching the spec's explicit examples
(earnings beat/miss, guidance cut/raise, M&A, regulatory action, analyst
upgrade/downgrade, executive change, product launch, litigation).

Input: a single article (headline + summary) — same per-article unit
`category.py` already uses.

Output: a single categorical string label (not a numeric score), e.g.
"EARNINGS_BEAT", "GUIDANCE_CUT", "OTHER".
"""

from __future__ import annotations

# Ordered waterfall, first match wins — same mechanism as category.py's
# CATEGORY_KEYWORDS. More specific event types are listed before more
# generic ones so e.g. "beat" doesn't shadow "raised guidance".
EVENT_TYPE_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("GUIDANCE_RAISE", ("raised guidance", "raises guidance", "guidance raised", "guidance hike")),
    ("GUIDANCE_CUT", ("cut guidance", "cuts guidance", "guidance cut", "lowered guidance", "guidance lowered")),
    ("EARNINGS_BEAT", ("beat estimates", "beats estimates", "beat expectations", "earnings beat", "profit beat")),
    ("EARNINGS_MISS", ("miss estimates", "misses estimates", "miss expectations", "earnings miss", "missed estimates")),
    ("ANALYST_UPGRADE", ("upgraded to", "analyst upgrade", "upgrades rating", "raised to buy", "raised to overweight")),
    ("ANALYST_DOWNGRADE", ("downgraded to", "analyst downgrade", "downgrades rating", "cut to sell", "cut to underweight")),
    ("MA_ANNOUNCEMENT", ("acquisition", "acquires", "to acquire", "merger", "to merge", "takeover bid", "buyout offer")),
    ("REGULATORY_ACTION", ("sec investigation", "sec probe", "doj investigation", "antitrust lawsuit", "regulatory probe", "fined by", "consent decree")),
    ("EXECUTIVE_CHANGE", ("steps down", "resigns as ceo", "names new ceo", "appoints ceo", "ceo resignation", "executive departure")),
    ("PRODUCT_LAUNCH", ("unveils", "launches new", "product launch", "announces new product", "rolls out")),
    ("LITIGATION", ("lawsuit", "sues", "sued by", "class action", "files suit")),
]


def classify_event_type(headline: str, summary: str, default: str = "OTHER") -> str:
    """Return a fine-grained event-type label for a single article.

    Waterfall matching identical in spirit to `category.refine_category`:
    first matching keyword group wins, case-insensitive substring match.
    """
    lower = f"{headline} {summary}".lower()
    for label, keywords in EVENT_TYPE_KEYWORDS:
        if any(kw in lower for kw in keywords):
            return label
    return default
