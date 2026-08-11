"""Cross-angle consensus check (Phase 8, New-talk-agents/new-thinking/
new-restructure/phases/phase-8-summary-agent-polish/): "do independent
methods agree right now" -- given two angles' real values for the same
ticker, report agree/diverge/insufficient_data, never forcing a binary
outcome when either angle has no real data. Deliberately deterministic
Python, not an LLM judgment call -- same reasoning as Phase 6's THGATE
near-duplicate check: a comparison rule that could silently drift call to
call would undermine the exact grounding discipline this is meant to
protect.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Companion config file, not embedded in a prompt -- same pattern as
# skills/strategy-tags/tags.yaml (02-guard-rail.md). Which categorical
# labels count as "adjacent enough to agree" is a judgment call that will
# need tuning as more angle pairs get wired in; a config file can be
# corrected without redeploying the prompt.
DEFAULT_ADJACENCY_PATH = Path(__file__).parent / "angle_consensus_adjacency.yaml"

# Provisional, not tuned -- same "flag it, don't pretend it's settled"
# discipline as every other un-pinned threshold across this build.
DEFAULT_MAGNITUDE_TOLERANCE = 0.15

INSUFFICIENT_DATA = "insufficient_data"
AGREE = "agree"
DIVERGE = "diverge"


@dataclass
class ConsensusResult:
    outcome: str  # "agree" | "diverge" | "insufficient_data"
    reasoning: str
    angle_a_name: str
    angle_b_name: str
    angle_a_value: Any
    angle_b_value: Any


def _insufficient(
    angle_a_name: str, angle_b_name: str, angle_a_row_count: int, angle_b_row_count: int,
    angle_a_value: Any = None, angle_b_value: Any = None,
) -> ConsensusResult:
    empty = []
    if angle_a_row_count <= 0:
        empty.append(angle_a_name)
    if angle_b_row_count <= 0:
        empty.append(angle_b_name)
    return ConsensusResult(
        outcome=INSUFFICIENT_DATA,
        reasoning=f"insufficient data to compare -- {', '.join(empty)} has row_count 0",
        angle_a_name=angle_a_name, angle_b_name=angle_b_name,
        angle_a_value=angle_a_value, angle_b_value=angle_b_value,
    )


def compare_directional(
    angle_a_name: str, angle_a_row_count: int, angle_a_value: float,
    angle_b_name: str, angle_b_row_count: int, angle_b_value: float,
) -> ConsensusResult:
    """Directional angles (forecast up/down): compare sign."""
    if angle_a_row_count <= 0 or angle_b_row_count <= 0:
        return _insufficient(angle_a_name, angle_b_name, angle_a_row_count, angle_b_row_count, angle_a_value, angle_b_value)

    sign_a = (angle_a_value > 0) - (angle_a_value < 0)
    sign_b = (angle_b_value > 0) - (angle_b_value < 0)
    outcome = AGREE if sign_a == sign_b else DIVERGE
    return ConsensusResult(
        outcome=outcome,
        reasoning=(
            f"{angle_a_name}={angle_a_value:g} vs {angle_b_name}={angle_b_value:g} -- "
            f"{'same' if outcome == AGREE else 'opposite'} direction"
        ),
        angle_a_name=angle_a_name, angle_b_name=angle_b_name,
        angle_a_value=angle_a_value, angle_b_value=angle_b_value,
    )


def compare_magnitude(
    angle_a_name: str, angle_a_row_count: int, angle_a_value: float,
    angle_b_name: str, angle_b_row_count: int, angle_b_value: float,
    *, tolerance: float = DEFAULT_MAGNITUDE_TOLERANCE,
) -> ConsensusResult:
    """Magnitude angles (a numeric forecast value): compare relative
    distance against a stated tolerance, not exact equality."""
    if angle_a_row_count <= 0 or angle_b_row_count <= 0:
        return _insufficient(angle_a_name, angle_b_name, angle_a_row_count, angle_b_row_count, angle_a_value, angle_b_value)

    denom = max(abs(angle_a_value), abs(angle_b_value), 1e-9)
    relative_distance = abs(angle_a_value - angle_b_value) / denom
    outcome = AGREE if relative_distance <= tolerance else DIVERGE
    return ConsensusResult(
        outcome=outcome,
        reasoning=(
            f"{angle_a_name}={angle_a_value:g} vs {angle_b_name}={angle_b_value:g} -- "
            f"relative distance {relative_distance:.2%} "
            f"{'within' if outcome == AGREE else 'exceeds'} tolerance {tolerance:.0%}"
        ),
        angle_a_name=angle_a_name, angle_b_name=angle_b_name,
        angle_a_value=angle_a_value, angle_b_value=angle_b_value,
    )


def load_adjacency_table(path: Path | None = None) -> dict[str, Any]:
    import yaml

    p = path or DEFAULT_ADJACENCY_PATH
    if not p.exists():
        return {}
    with open(p, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _adjacent(adjacency: dict[str, Any], angle_a_name: str, label_a: str, angle_b_name: str, label_b: str) -> bool:
    forward = adjacency.get(angle_a_name, {}).get(angle_b_name, {})
    if label_a in forward:
        return label_b in (forward[label_a] or [])
    backward = adjacency.get(angle_b_name, {}).get(angle_a_name, {})
    if label_b in backward:
        return label_a in (backward[label_b] or [])
    return False


def compare_categorical(
    angle_a_name: str, angle_a_row_count: int, angle_a_value: str,
    angle_b_name: str, angle_b_row_count: int, angle_b_value: str,
    *, adjacency_table: dict[str, Any] | None = None,
) -> ConsensusResult:
    """Categorical angles (regime label, lifecycle stage): exact-match, or
    a stated adjacency rule from the companion config file -- never an
    LLM judgment call by call (02-guard-rail.md: 'the same two angles
    could be scored as agreeing one day and diverging the next with no
    code change' otherwise)."""
    if angle_a_row_count <= 0 or angle_b_row_count <= 0:
        return _insufficient(angle_a_name, angle_b_name, angle_a_row_count, angle_b_row_count, angle_a_value, angle_b_value)

    adjacency = adjacency_table if adjacency_table is not None else load_adjacency_table()
    exact = angle_a_value == angle_b_value
    agree = exact or _adjacent(adjacency, angle_a_name, str(angle_a_value), angle_b_name, str(angle_b_value))
    outcome = AGREE if agree else DIVERGE
    return ConsensusResult(
        outcome=outcome,
        reasoning=(
            f"{angle_a_name}={angle_a_value!r} vs {angle_b_name}={angle_b_value!r} -- "
            f"{'exact match' if exact else ('adjacent per config' if agree else 'not adjacent per config')}"
        ),
        angle_a_name=angle_a_name, angle_b_name=angle_b_name,
        angle_a_value=angle_a_value, angle_b_value=angle_b_value,
    )
