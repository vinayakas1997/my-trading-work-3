"""Method 2 — Named Entity Recognition (countries, organizations, people, tickers).

Spec: New-talk-/Final-implementation/01-present-considerations/02-named-entity-recognition.md

Build call: **adapt**. `vinu-news` already has a working rule/dictionary
NER extractor for people + countries
(`vinu_news/analysis/post_enrichment/ner/extract_entities.py`, backed by
`people_map.py`/`country_map.py`) and a separate, already-good ticker
regex extractor (`vinu_news/analysis/enrichment/ticker_extractor.py`) —
per the spec's own note, "the ticker extraction regex is likely
redundant with whatever vinu-news already uses ... check that before
porting, don't duplicate," so this module reuses `extract_tickers`
directly rather than porting the spec's separate ticker regex.
Organizations were the one genuinely missing category (per the spec's
notes: "currently nothing in vinu-news/vinu-initial-analysis knows *who*
an article is about beyond the ticker(s)") — added as a new
`ORG_MAP` dictionary (`ner/org_map.py`) in the same style as the existing
`people_map.py`/`country_map.py`, not a new extraction mechanism.

This module is a thin adapter: it calls the three existing extractors,
adds the organization lookup, and applies the spec's per-article cap
(5 per category, deduplicated) plus the batch-level top-10 rollup that
didn't exist anywhere in the codebase before.

Note: the existing `extract_entities()` matches people/country phrases
via plain substring containment (no word-boundary regex) — the spec
calls for word-boundary matching on short patterns specifically to avoid
false positives like "rome" inside "jerome". Left as-is here (existing,
already-in-production behavior, exercised by `tests/analysis/test_ner.py`)
rather than changed, per this task's "wrap, don't rewrite" instruction.

Input: a single article (headline + summary) for `extract_entities_full`;
a batch of already-extracted per-article dicts for `aggregate_top_entities`.

Output: `extract_entities_full` -> dict of lists under `countries`,
`organizations`, `people`, `tickers` (deduplicated, capped at 5 each).
`aggregate_top_entities` -> dict of top-10 `(value, count)` pairs per
category across a batch.
"""

from __future__ import annotations

from collections import Counter

from vinu_news.analysis.enrichment.ticker_extractor import extract_tickers
from vinu_news.analysis.post_enrichment.ner.extract_entities import extract_entities
from vinu_news.analysis.post_enrichment.ner.org_map import ORG_MAP

MAX_PER_CATEGORY = 5
TOP_N = 10


def _extract_organizations(headline: str, summary: str) -> list[str]:
    text = f"{headline} {summary}".lower()
    seen: set[str] = set()
    orgs: list[str] = []
    for phrase, canonical in sorted(ORG_MAP.items(), key=lambda x: len(x[0]), reverse=True):
        if phrase in text and canonical not in seen:
            seen.add(canonical)
            orgs.append(canonical)
    return orgs


def extract_entities_full(
    headline: str, summary: str, watchlist: set[str] | None = None
) -> dict[str, list[str]]:
    """Structured entity dict for one article — countries/organizations/people/tickers.

    Deduplicated and capped at `MAX_PER_CATEGORY` per category, matching
    the spec's output format exactly (presence tags, no scores).
    """
    base = extract_entities(headline, summary)  # {"people": [...], "countries": [...]}
    organizations = _extract_organizations(headline, summary)
    tickers = extract_tickers(headline, summary, watchlist=watchlist)

    return {
        "countries": base["countries"][:MAX_PER_CATEGORY],
        "organizations": organizations[:MAX_PER_CATEGORY],
        "people": base["people"][:MAX_PER_CATEGORY],
        "tickers": tickers[:MAX_PER_CATEGORY],
    }


def aggregate_top_entities(
    batch_results: list[dict[str, list[str]]], top_n: int = TOP_N
) -> dict[str, list[tuple[str, int]]]:
    """Aggregate top-N most frequent entities per category across a batch.

    `batch_results` is a list of `extract_entities_full(...)` outputs.
    Returns, per category, a list of `(value, count)` pairs sorted by
    count descending (ties broken alphabetically for determinism).
    """
    counters: dict[str, Counter[str]] = {
        "countries": Counter(),
        "organizations": Counter(),
        "people": Counter(),
        "tickers": Counter(),
    }
    for result in batch_results:
        for category, counter in counters.items():
            counter.update(result.get(category, []))

    return {
        category: sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))[:top_n]
        for category, counter in counters.items()
    }
