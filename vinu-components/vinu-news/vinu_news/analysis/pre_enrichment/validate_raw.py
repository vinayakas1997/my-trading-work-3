"""Validate raw article dicts before rule enrichment."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

REQUIRED_KEYS = ("headline", "link", "source")


def validate_raw(raw: dict[str, Any]) -> bool:
    """Return True if raw dict has required non-empty fields."""
    for key in REQUIRED_KEYS:
        value = raw.get(key, "")
        if not value or not str(value).strip():
            return False
    return True


def validate_raw_batch(raw_articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Filter to valid raw articles; log dropped rows."""
    valid: list[dict[str, Any]] = []
    for raw in raw_articles:
        if validate_raw(raw):
            valid.append(raw)
        else:
            logger.warning(
                "Dropped invalid raw article: headline=%r link=%r",
                raw.get("headline"),
                raw.get("link"),
            )
    return valid
