"""Strip noise prefixes from headlines before dedup vectorization."""

from __future__ import annotations

import re

_PREFIX_PATTERN = re.compile(
    r"^(?:breaking|update|exclusive|alert|urgent|flash)\s*[:\-\|]\s*",
    re.IGNORECASE,
)
_BRACKET_PATTERN = re.compile(r"^\[[^\]]+\]\s*")


def clean_headline_for_dedup(headline: str) -> str:
    """Remove common prefixes; original headline stored in DB unchanged."""
    text = headline.strip()
    for _ in range(3):
        updated = _PREFIX_PATTERN.sub("", text).strip()
        updated = _BRACKET_PATTERN.sub("", updated).strip()
        if updated == text:
            break
        text = updated
    return text
