"""Open to close return."""

from __future__ import annotations

from vinu_features.compute.indicators._shared.rows import col

KIND = "open_close_return"
DESCRIPTION = "Open to close return"
PARAMS: dict = {}
OUTPUT_COLUMNS = ("open_close_return",)
EXAMPLES = ("open_close_return",)
LEGACY_ALIASES = {"open_close_return": {}}

FEATURE_NAMES = ("open_close_return",)
WARMUP_BARS = 1


def matches(name: str) -> bool:
    return name == "open_close_return"


def warmup_for(name: str) -> int:
    return 1


def compute(rows: list[dict], *, name: str) -> dict[str, list[float | None]]:
    open_, close = col(rows, "open"), col(rows, "close")
    out: list[float | None] = []
    for o, c in zip(open_, close):
        out.append((c - o) / o if o else None)
    return {name: out}
