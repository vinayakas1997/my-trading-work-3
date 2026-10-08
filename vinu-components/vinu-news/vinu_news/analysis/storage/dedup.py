"""Layer 2 of the news plan: the same item from the same source is one row.

A row keeps `first_seen_at` (when this system first saw it: the "known at" time), `last_seen_at` and `seen_count`. When the
source serves the same link again with the same text, only the last-seen time and the count move. When the text really
changes, the new text is stored as a new row linked to the old one (`revision_of`), the old row stays (`is_current = 0`) and
the new row gets its own first-seen time.

The fingerprint is deliberately small: lower-case words of the headline and the first part of the summary, punctuation and
spacing ignored, so a re-flowed or re-punctuated copy is the same item and a reworded one is a revision.
"""
from __future__ import annotations

import hashlib
import re

_WORDS = re.compile(r"[a-z0-9]+")
SUMMARY_CHARS = 2000


def content_hash(headline: str, summary: str) -> str:
    text = f"{headline or ''}␟{(summary or '')[:SUMMARY_CHARS]}".lower()
    words = _WORDS.findall(text)
    return hashlib.sha1(" ".join(words).encode("utf-8")).hexdigest()


def revision_id(previous_id: str, new_content_hash: str) -> str:
    """A new, repeatable id for a revision (the headline-and-time id can equal the old one when only the summary changed)."""
    return hashlib.sha256(f"{previous_id}:{new_content_hash}".encode("utf-8")).hexdigest()
