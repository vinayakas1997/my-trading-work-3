"""System manifest -- Decision 6 + Decision 7 of
missing-pieces-of-system/new-theory-of-trading/01-planning.md.

The one place to see "what a run actually used" -- angle inventory by
category, current model policy, active angle count, the recording
granularity in effect, and the evidence-table's live column count.
Lives in vinu-infra for the same reason model_policy.py does: it's a
direct reflection of that policy, and vinu-infra is the one dependency
already shared across components.

This module does not discover angles itself (that's
vinu-initial-analysis's AngleRunner._discover()'s job) -- it takes an
already-discovered angle list (each entry a dict with at least `name`
and `spec`, i.e. the parsed spec.yaml) and reports on it. Kept this way
so vinu-infra never needs to import vinu-initial-analysis to build a
manifest for it.
"""

from __future__ import annotations

import os
from typing import Any

from vinu_infra.model_policy import models_enabled, policy_version

# Decision 2: swing-style must-conditions record on 15-minute bars, not
# 1-minute. Overridable via env for the one carved-out exception Decision
# 2 itself names (a genuinely intraday/scalping strategy would need its
# own separate granularity decision) -- not meant to be casually changed.
RECORDING_TIME_FORMAT: str = os.getenv("VINU_RECORDING_TIME_FORMAT", "15min")

# Decision 1 (raw trigger + supporting-indicator snapshot) + Decision 7
# (policy_version stamped per row): the fixed, non-indicator columns
# every evidence-table row carries regardless of how many supporting
# indicators are active. One column per active supporting indicator
# (Decision 3: one JSON column per indicator/angle) is added on top of
# this fixed count.
FIXED_EVIDENCE_COLUMNS: list[str] = [
    "trigger_id",
    "symbol",
    "trigger_time",
    "must_condition",
    "max_favorable_excursion",
    "max_adverse_excursion",
    "return_at_horizon",
    "policy_version",
]

# Decision 5: permanently excluded regardless of category tag or the
# MODELS switch -- these three are pinned to a statistical fallback
# proxy by design (a real dependency conflict, not a temporary error
# path), and would otherwise silently masquerade as independent model
# opinions in the evidence table.
PERMANENTLY_DISABLED_ANGLES: frozenset[str] = frozenset({"moirai", "moment", "lag_llama"})


def _category(angle: dict[str, Any]) -> str:
    spec = angle.get("spec") or {}
    return spec.get("category", "raw_data")


def _time_formats(angle: dict[str, Any]) -> list[str]:
    spec = angle.get("spec") or {}
    return list(spec.get("time_formats") or [])


def resolve_active_angles(angles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The angles that will actually run given the current model policy:
    permanently-disabled angles are always excluded; model-category
    angles are excluded on top of that when models_enabled() is false."""
    active = []
    for angle in angles:
        name = angle.get("name", "")
        if name in PERMANENTLY_DISABLED_ANGLES:
            continue
        if _category(angle) == "model" and not models_enabled():
            continue
        active.append(angle)
    return active


def build_manifest(angles: list[dict[str, Any]]) -> dict[str, Any]:
    """The full startup manifest for a discovered angle list.

    `angles` is AngleRunner.list_angles()'s own shape: a list of dicts
    with at least `name` and `spec` (the parsed spec.yaml, expected to
    carry a `category` field per Decision 4 -- angles missing it are
    treated as `raw_data`, the least surprising default)."""
    total = len(angles)
    by_category: dict[str, int] = {}
    for angle in angles:
        name = angle.get("name", "")
        cat = "disabled" if name in PERMANENTLY_DISABLED_ANGLES else _category(angle)
        by_category[cat] = by_category.get(cat, 0) + 1

    active = resolve_active_angles(angles)
    active_names = {a.get("name", "") for a in active}

    unsupported_time_format = sorted(
        a.get("name", "")
        for a in active
        if _time_formats(a) and RECORDING_TIME_FORMAT not in _time_formats(a)
    )

    evidence_column_count = len(FIXED_EVIDENCE_COLUMNS) + len(active)

    return {
        "policy_version": policy_version(),
        "models_enabled": models_enabled(),
        "angle_inventory": {
            "total": total,
            "by_category": by_category,
            "permanently_disabled": sorted(PERMANENTLY_DISABLED_ANGLES & {a.get("name", "") for a in angles}),
        },
        "active_angle_count": len(active),
        "active_angle_names": sorted(active_names),
        "recording_time_format": RECORDING_TIME_FORMAT,
        "angles_missing_recording_time_format": unsupported_time_format,
        "evidence_table": {
            "fixed_columns": len(FIXED_EVIDENCE_COLUMNS),
            "active_indicator_columns": len(active),
            "total_columns": evidence_column_count,
            "note": (
                "Counts angle-based supporting indicators only -- the "
                "non-angle indicators in all-possible-supporting-"
                "indicators.md (technical/volume/volatility/microstructure/"
                "context/meta) aren't angle-discovered and aren't counted "
                "here yet."
            ),
        },
    }
