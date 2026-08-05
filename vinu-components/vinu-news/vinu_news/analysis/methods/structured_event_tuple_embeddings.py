"""Method 8 — Structured Event-Tuple Extraction (Actor, Action, Object).

Spec: New-talk-/Final-implementation/01-present-considerations/08-structured-event-tuple-embeddings.md

Per the task scope (and the spec's own "Requirements"/"Notes" sections),
only the non-LLM extraction step is implemented — no neural embedding
step. The spec explicitly recommends this as the first-effort version:
"extract just the (Actor, Action, Object) tuple and the event-type
category *without* building the neural embedding step ... the version
that survives both Final-implementation limitations." The embedding step
itself is also explicitly out of scope regardless: it "requires training
a small neural network on a labeled/aligned dataset of (event,
subsequent price move) pairs" — a training pipeline, not something a
single ingest-time `compute()` function can do, and the spec flags the
data-sufficiency question as unresolved ("Unclear yet whether this
project's article volume for AAPL/TSLA/JNJ alone is sufficient").

Build call: **build new, but composed almost entirely from existing/
sibling method building blocks** — not a full dependency-parsing/SRL
pipeline. The spec's extraction path that "survives limitation #1" is
SRL/dependency parsing (spaCy or similar); that's a real NLP model
dependency (and network fetch for pipeline weights) this dev environment
can't verify is available, and none of the rest of `vinu-news`'s
Fincept-derived pipeline uses a parser dependency anywhere — every other
enrichment module (`category.py`, `priority.py`, `threat.py`, the NER
dictionaries) is deliberately regex/dictionary-based instead. In that
spirit, this module extracts the tuple with a lightweight rule-based
heuristic instead of a real parser:
- **Actor/Object** slots are filled from this project's own entity
  extraction — method 2 (`named_entity_recognition.extract_entities_full`,
  itself reusing the existing NER dictionaries) — exactly the input the
  spec's own notes point at: "Actor/Object slots in an event tuple are
  exactly what this entity extraction produces."
- **Action** is a curated verb-phrase lexicon, same waterfall-matching
  style as `category.py`/`priority.py`/`threat.py`.
- **event_type** is method 1 (`event_type_classification.classify_event_type`),
  directly reused rather than re-derived, matching the spec's stated
  output format for the partial version: "same output shape as
  01-event-type-classification.md."
This trades true dependency-parsed subject/object roles for something
much cheaper that still produces a genuine structured tuple from
existing building blocks; a real SRL/parser upgrade path is still open
if entity-proximity heuristics prove too coarse.

Input: a single article's text (headline + summary) — the extraction
step's unit per the spec.

Output: `{"actor": str|None, "action": str|None, "object": str|None,
"event_type": str}` — the raw tuple plus categorical event-type tag, no
embedding vector.
"""

from __future__ import annotations

from vinu_news.analysis.methods.event_type_classification import classify_event_type
from vinu_news.analysis.methods.named_entity_recognition import extract_entities_full

# Ordered waterfall of action verb-phrases -> canonical action label.
ACTION_VERBS: list[tuple[str, str]] = [
    ("sues", "sues"),
    ("sued by", "sued_by"),
    ("files suit", "sues"),
    ("acquires", "acquires"),
    ("to acquire", "acquires"),
    ("merges with", "merges_with"),
    ("beats estimates", "beats_estimates"),
    ("beat estimates", "beats_estimates"),
    ("misses estimates", "misses_estimates"),
    ("miss estimates", "misses_estimates"),
    ("raises guidance", "raises_guidance"),
    ("raised guidance", "raises_guidance"),
    ("cuts guidance", "cuts_guidance"),
    ("cut guidance", "cuts_guidance"),
    ("upgrades", "upgrades"),
    ("upgraded", "upgrades"),
    ("downgrades", "downgrades"),
    ("downgraded", "downgrades"),
    ("fined", "fined"),
    ("fines", "fines"),
    ("launches", "launches"),
    ("unveils", "unveils"),
    ("fires", "fires"),
    ("resigns", "resigns"),
    ("steps down", "resigns"),
    ("appoints", "appoints"),
    ("investigates", "investigates"),
    ("probes", "investigates"),
]


def _find_action(lower_text: str) -> tuple[str | None, int]:
    """Return the first-matching action label and its character position."""
    best_pos = len(lower_text) + 1
    best_action: str | None = None
    for phrase, label in ACTION_VERBS:
        pos = lower_text.find(phrase)
        if pos != -1 and pos < best_pos:
            best_pos = pos
            best_action = label
    return best_action, best_pos


def extract_event_tuple(headline: str, summary: str) -> dict:
    """Extract a lightweight (Actor, Action, Object) tuple plus event-type tag."""
    combined = f"{headline} {summary}"
    lower_text = combined.lower()

    entities = extract_entities_full(headline, summary)
    candidates = entities["people"] + entities["organizations"] + entities["tickers"]

    def position(candidate: str) -> int:
        pos = lower_text.find(candidate.lower())
        return pos if pos != -1 else len(lower_text) + 1

    ordered_candidates = sorted(dict.fromkeys(candidates), key=position)
    ordered_candidates = [c for c in ordered_candidates if position(c) <= len(lower_text)]

    action, action_pos = _find_action(lower_text)

    actor = ordered_candidates[0] if ordered_candidates else None
    obj = None
    for candidate in ordered_candidates[1:]:
        if candidate != actor:
            obj = candidate
            break

    event_type = classify_event_type(headline, summary)

    return {"actor": actor, "action": action, "object": obj, "event_type": event_type}
