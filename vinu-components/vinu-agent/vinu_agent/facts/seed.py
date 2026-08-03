"""One-time seed data for the Facts & Limitations Registry — migrating what's
already proven in this repo, not new research. See `registry.py`'s module
docstring and `03-on-agent-consiuness`/`04-agentic-still-refinement` for
where each of these came from.
"""

from __future__ import annotations

from .registry import Fact, FactsRegistry

SEED_FACTS: list[dict] = [
    {
        "statement": (
            "Direction prediction from sentiment_score or FinBERT's "
            "finbert_score does not beat a coin flip. Tested twice "
            "(rule-based sentiment, then FinBERT) against already-significant "
            "events on AAPL/TSLA/JNJ — ~50% sign-agreement rate, all "
            "correlations p > 0.1. significance_score is proven for "
            "magnitude/surprise prioritization only — do not use it, or "
            "either sentiment score, to predict the SIGN of a price move."
        ),
        "kind": "disproven",
        "symbols": ["AAPL", "TSLA", "JNJ"],
        "signals": ["sentiment_score", "finbert_score", "significance_score"],
        "evidence_ref": "01-the-stage-2-claude/full-plan.md:68-74",
        "established_date": "2026-08-02",
    },
    {
        "statement": (
            "This agent previously fabricated a stock price for JNJ "
            "($162.45, never fetched via a tool call; the real value was "
            "~$267.16) and repeated it across 13 consecutive simulated days "
            "without ever calling get_stock_price. Never state a symbol's "
            "price from memory or training data — only from a fresh tool "
            "call this session or the ground-truth block."
        ),
        "kind": "known-bug",
        "symbols": ["JNJ"],
        "signals": [],
        "evidence_ref": "the-project-vision/the-premarket-agents-answers-from-replay.md",
        "established_date": "2026-07-01",
    },
    {
        "statement": (
            "In a 20-day replay, this agent went silent (zero tool calls) "
            "for 16 of 20 simulated days. Absence of tool calls in recent "
            "history is not evidence that nothing needs checking — a quiet "
            "session is a prompt to re-verify state, not confirmation that "
            "nothing changed."
        ),
        "kind": "known-bug",
        "symbols": [],
        "signals": [],
        "evidence_ref": "the-project-vision/the-premarket-agents-answers-from-replay.md",
        "established_date": "2026-07-01",
    },
]


def seed_if_empty(registry: FactsRegistry) -> int:
    """Insert SEED_FACTS if the registry has no active rows yet. Idempotent by
    count (not content) — safe to call on every process startup."""
    if registry.count_active() > 0:
        return 0
    for data in SEED_FACTS:
        registry.add_fact(Fact(id="", **data))
    return len(SEED_FACTS)
