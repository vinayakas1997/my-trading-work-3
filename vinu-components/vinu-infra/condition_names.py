"""One definition of a must-condition's name, shared by the writer (live poller records a trigger under these
names) and the reader (the agent's context tool filters evidence to the strategy's own names). Two copies of
this rule would let them drift apart and silently match nothing."""

from __future__ import annotations

from typing import Any


def condition_name(condition: dict[str, Any]) -> str:
    """`{source}.{key}_{operator}_{value}`, derived from the structured condition (no authored name needed)."""
    source = condition.get("source", "live_indicators")
    key = condition.get("key", "?")
    operator = condition.get("operator", "gt")
    value = condition.get("value")
    return f"{source}.{key}_{operator}_{value}"
