"""Analysis T -- the LESSON snapshots as a free maturity-signal baseline
check. Design reference: missing-pieces-of-system/maturity-agentic-
system/thinking-1/02-decided-pattern/25-A-Y-details/
06-external-signal-cross-check.md ("T").

**Structurally blocked, confirmed 2026-09-19**: nothing to compare
against, since `MaturityAssessor` didn't exist. **Built 2026-09-20**, the
same day `_maturity_assessor.py` (this module's own new sibling) was
built, once that gave a real tier to compare LESSON against.

**"Direction" comparison, reasoned through**: the design doc's Condition
is "the two disagree in direction (e.g. LESSON implies improving while
MaturityAssessor implies degrading) ... both sides are already summary
judgments." `MaturityAssessor.assess()`'s tier is a *level*
(cold_start/paper_only/early_live/mature), not itself a direction, and
the design doc explicitly forbids persisting it as a new store (it's a
recomputable read-model) -- so there's no natural "yesterday's tier vs
today's tier" trend to read the way every other analyst's `compute_trend()`
gets one for free from `reflection_beliefs`. Rather than invent a
persisted trend just for this comparison, `_maturity_assessor.
recent_form_reading()` gives MaturityAssessor its own crude, unpersisted
"recent form" read from the same-shaped raw material LESSON uses: the
most recent `MIN_RECENT_FORM_ENTRIES` real calibration entries
system-wide (win/loss on `directional_correct`), directly comparable to
LESSON's own `last5` win/loss string -- both are real, both are crude by
design, both are "already summary judgments," matching the doc's own
framing exactly rather than reaching for something more sophisticated on
just one side.

**Disagreement, defined narrowly**: only "one side says improving, the
other says degrading" counts -- `{lesson_reading, assessor_reading} ==
{"improving", "degrading"}`. A "flat" on either side is not itself
alarming (the doc's own example names an improving/degrading
contradiction specifically), so it's excluded from the disagreement set.

**Storage**: `scope_type=system`, `scope_key="lesson_baseline_check"`
(exactly as the design doc specifies). `evidence_count` = LESSON's own
`closed` count (the real trade volume backing LESSON's read at the point
this comparison fires -- LESSON itself never writes below
`VINU_LESSON_MIN_TRADES`, so any file found already clears a real floor).
`domain_floor_breached` = disagreement itself, forcing significance the
same direct way A's Brier floor and V's `correlation <= 0` do -- a real
disagreement between two independent judgments is the significant event
itself, not something PSI/trend needs to detect.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from vinu_infra.reflection import Finding, POLARITY_LOWER_IS_WORSE

from vinu_reflection.reflection import _maturity_assessor

ANALYST_NAME = "lesson_maturity_baseline_check"
CLUSTER = "External-Signal Cross-Check"
METRIC_NAME = "lesson_maturity_agreement"


def _latest_lesson(lessons_dir: Path) -> Optional[dict]:
    if not lessons_dir.is_dir():
        return None
    files = sorted(lessons_dir.glob("*LESSON_*.json"))
    if not files:
        return None
    try:
        return json.loads(files[-1].read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _lesson_reading(lesson: dict) -> str:
    last5 = lesson.get("last5") or ""
    wins = last5.count("W")
    losses = last5.count("L")
    if wins > losses:
        return "improving"
    if losses > wins:
        return "degrading"
    return "flat"


def run(
    data_root_paths: dict[str, Path],
    service_clients: Optional[dict[str, Any]] = None,
) -> list[Finding]:
    """`data_root_paths["vinu_live"]` must point at a mounted copy of
    vinu-live's own data root -- same mount every other vinu-live-reading
    analyst in this service already uses; LESSON snapshots live at
    `<vinu_live_data_root>/lessons/*LESSON_*.json`
    (`vinu_live/lesson_worker.py::write_lesson()`)."""
    live_root = Path(data_root_paths["vinu_live"])
    lesson = _latest_lesson(live_root / "lessons")
    if lesson is None:
        return []

    assessor_reading = _maturity_assessor.recent_form_reading(data_root_paths)
    if assessor_reading is None:
        return []

    lesson_reading = _lesson_reading(lesson)
    assessment = _maturity_assessor.assess(data_root_paths)
    disagree = {lesson_reading, assessor_reading} == {"improving", "degrading"}
    agree = not disagree

    return [
        Finding(
            analyst_name=ANALYST_NAME,
            cluster=CLUSTER,
            scope_type="system",
            scope_key="lesson_baseline_check",
            signal_json={
                "lesson_reading": lesson_reading,
                "maturity_reading": assessor_reading,
                "maturity_tier": assessment.tier,
                "agree": agree,
                "lesson_last5": lesson.get("last5"),
            },
            evidence_count=int(lesson.get("closed", 0) or 0),
            primary_metric=1.0 if agree else 0.0,
            metric_name=METRIC_NAME,
            psi=0.0,
            domain_floor_breached=disagree,
            narrative=(
                f"LESSON reads '{lesson_reading}' (last5={lesson.get('last5')!r}) vs "
                f"MaturityAssessor's recent-form read '{assessor_reading}' "
                f"(tier={assessment.tier}): {'agree' if agree else 'DISAGREE'}"
            ),
        )
    ]


def seed_reference_config(reflection_store) -> None:
    reflection_store.upsert_reference_config(
        analyst_name=ANALYST_NAME,
        scope_type="system",
        metric_name=METRIC_NAME,
        metric_polarity=POLARITY_LOWER_IS_WORSE,
        reference_window_definition="lesson_last5_vs_maturity_assessor_recent_form",
        reason=(
            "T: LESSON's crude win/loss read and MaturityAssessor's own recent-form "
            "read disagreeing on direction is a real sanity-check failure worth flagging"
        ),
        updated_by=ANALYST_NAME,
    )
