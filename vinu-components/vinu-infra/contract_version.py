"""Deterministic contract/schema version stamps -- item #17's "confirmed
gap, not a new item" (system-wide-audit-and-design/
02-open-questions-strategy-and-simulation.md): "no policy_version/schema-
version field threads through the whole agent->research->simulator
chain, so a schema change on one side has nothing automated to catch it
before silently breaking the other."

A prior pass already built strong TEST-time protection for this
(`vinu-agent/tests/test_research_contract.py`,
`vinu-research/tests/test_simulator_contract.py` -- import-based, they
validate real payload-building code against the real pydantic models).
That catches drift the instant both sides' code is checked out together
in one test run. What it can't catch: DEPLOY-time drift, where the three
services run as independently-versioned processes and one falls behind
the others. This module is the piece that closes that narrower, real
remaining gap -- a version stamp threaded through the actual live
request/response, not just present in a test file.

Deliberately NOT the same mechanism as `vinu_infra.model_policy`'s
`policy_version()`, despite the name-adjacent concept -- that one stamps
which ML model checkpoint/config is active, a completely different
question. Reusing it here would conflate two unrelated concerns that
happen to share a word.

Confirmed approach (2026-09-28): a deterministic hash of the pydantic
model's own JSON schema, not a manually-bumped integer -- the version
changes automatically the instant a field's shape actually changes, so
nobody can forget to bump it (the same human-discipline gap this finding
exists because of).
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


def contract_version(model_cls: Any) -> str:
    """Deterministic short hash of a pydantic model's field shape
    (`model_json_schema()`). Two versions of a model with the same
    fields (name, type, required-ness, default) produce the same hash;
    any real shape change produces a different one.

    `title`/`description` are stripped before hashing -- purely cosmetic
    metadata (a tweaked docstring, a renamed class) that doesn't change
    what the contract actually accepts, so it must not change the
    version on its own."""
    schema = model_cls.model_json_schema()
    schema.pop("title", None)
    schema.pop("description", None)
    _strip_cosmetic(schema)
    material = json.dumps(schema, sort_keys=True)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:12]


def _strip_cosmetic(node: Any) -> None:
    """Recurses into nested `$defs`/`properties` (which pydantic emits
    for any nested model) so a docstring change several levels down
    doesn't shift the top-level hash either."""
    if isinstance(node, dict):
        node.pop("title", None)
        node.pop("description", None)
        for value in node.values():
            _strip_cosmetic(value)
    elif isinstance(node, list):
        for item in node:
            _strip_cosmetic(item)
