"""HTML stripping and summary truncation (Fincept Section 6A)."""

import re

MAX_SUMMARY_LEN = 300
HTML_TAG_PATTERN = re.compile(r"<[^>]*>")


def clean_summary(text: str) -> str:
    """Strip HTML tags, collapse whitespace, truncate to 300 characters."""
    if not text:
        return ""
    cleaned = HTML_TAG_PATTERN.sub("", text)
    cleaned = " ".join(cleaned.split())
    return cleaned[:MAX_SUMMARY_LEN]
