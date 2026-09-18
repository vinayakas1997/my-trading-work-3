"""Analysis H, governance piece -- for each real edit to a risk-relevant
skill file, compares realized trade-outcome quality in the trailing
window after the edit against the trailing window before it.
Event-triggered, not cycle-gated, same shape as N (kill-switch
retrospective) -- see 04-reference-baseline-config.md's `n/a` trend note
for the same reason. Design reference:
missing-pieces-of-system/maturity-agentic-system/thinking-1/02-decided-pattern/
25-A-Y-details/05-governance-freshness.md ("H", governance piece).

**Scoping correction found while implementing**: `trade_score_calibration_history`
rows (`vinu-research/vinu_research/trade_score_calibration.py`) carry no
artifact/strategy id at all -- only `timestamp, direction,
actual_return_pct, tier, total_score`, sub-scores. There is no real way
to scope the before/after comparison to "whatever artifact/strategy
family the edited rule affects," as the design doc describes -- the
join key it assumes doesn't exist in this file. Implemented as a
system-wide before/after comparison instead (every closed trade's
outcome quality, not filtered by strategy); `affected_strategy_family`
dropped from `signal_json` accordingly.

**Known trend-field caveat, not introduced here**: `04-reference-baseline-config.md`
marks this piece's polarity `n/a` ("event-triggered per skill-edit, not
a recurring belief; no trend to compute") -- `write_finding()`'s shared
path has no explicit "n/a" trend value yet, so `reflection_beliefs.trend`
for this scope will end up comparing this edit's delta against the
*previous* edit's delta rather than meaning anything continuous. Same
pre-existing gap N already has; not solved here.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from vinu_infra.reflection import (
    Finding,
    POLARITY_LOWER_IS_WORSE,
    population_stability_index,
)

from vinu_agent.agent.skill_audit import AUDITED_SKILL_PATHS, SkillAuditStore
from vinu_research.trade_score_calibration import read_history

ANALYST_NAME = "governance_freshness"
CLUSTER = "Governance & Freshness"
METRIC_NAME = "outcome_delta_before_after"
SCOPE_KEY = "skill_rule_edits"

# Trailing window on each side of an edit -- same order of magnitude as
# every other trailing-window analysis in this service (D/A/C all use
# 30), scaled down slightly since skill edits are deliberately rare
# events with a smaller natural comparison window.
WINDOW = 20
MIN_WINDOW = 10


def _mean(values: list[float]) -> float:
    return sum(values) / len(values)


def _trade_score_calibration_history_path() -> Path:
    """Mirrors `trade_score_calibration.py`'s own `DEFAULT_HISTORY_PATH`
    logic, but resolved fresh at call time instead of once at import
    time -- `DEFAULT_HISTORY_PATH` is a module-level constant computed
    from `os.environ` the moment that module first gets imported
    anywhere in the process, which is fine for a real long-running
    worker (the env is already set before any import happens) but wrong
    for tests that need a different data root per test within the same
    pytest process. Same "resolve fresh, don't trust a frozen constant"
    reasoning `research_link.py`'s own `_research_data_root()` already
    uses."""
    explicit = os.environ.get("VINU_TRADE_SCORE_CALIBRATION_HISTORY", "").strip()
    if explicit:
        return Path(explicit)
    research_root = os.environ.get("VINU_RESEARCH_DATA_ROOT", "").strip()
    if research_root:
        return Path(research_root) / "trade_score_calibration_history.jsonl"
    return Path.home() / ".vinu-research" / "trade_score_calibration_history.jsonl"


def _parse_detected_at(detected_at: str) -> Optional[float]:
    try:
        return (
            datetime.strptime(detected_at, "%Y-%m-%dT%H:%M:%SZ")
            .replace(tzinfo=timezone.utc)
            .timestamp()
        )
    except ValueError:
        return None


def run(
    data_root_paths: dict[str, Path],
    service_clients: Optional[dict[str, Any]] = None,
) -> list[Finding]:
    """`data_root_paths["vinu_agent"]` for `skill_audit.db`.
    `trade_score_calibration_history.jsonl` is read via vinu-research's
    `read_history()`, given an explicit path resolved fresh from
    `VINU_RESEARCH_DATA_ROOT`/`VINU_TRADE_SCORE_CALIBRATION_HISTORY`
    (this container's environment -- docker-compose.yml mounts
    `./data/research` read-only at `/research-data`) by
    `_trade_score_calibration_history_path()` above, rather than trusting
    `read_history()`'s own module-level default (frozen at import time,
    see that helper's docstring)."""
    data_root = Path(data_root_paths["vinu_agent"])
    audit_store = SkillAuditStore(data_root / "skill_audit.db")

    edits = []
    for skill_path in AUDITED_SKILL_PATHS:
        edits.extend(audit_store.get_history(skill_path))
    if not edits:
        return []

    history = sorted(
        read_history(log_path=_trade_score_calibration_history_path()),
        key=lambda r: r.get("timestamp", 0.0),
    )
    if len(history) < 2 * MIN_WINDOW:
        return []

    findings: list[Finding] = []
    for edit in edits:
        edit_ts = _parse_detected_at(edit.detected_at)
        if edit_ts is None:
            continue

        before = [r for r in history if r.get("timestamp", 0.0) < edit_ts][-WINDOW:]
        after = [r for r in history if r.get("timestamp", 0.0) >= edit_ts][:WINDOW]
        if len(before) < MIN_WINDOW or len(after) < MIN_WINDOW:
            continue

        before_quality = [1.0 if r.get("actual_return_pct", 0.0) > 0 else 0.0 for r in before]
        after_quality = [1.0 if r.get("actual_return_pct", 0.0) > 0 else 0.0 for r in after]
        before_mean = _mean(before_quality)
        after_mean = _mean(after_quality)
        delta = after_mean - before_mean

        psi = population_stability_index(
            before_quality, after_quality, bin_count=2, min_samples_per_bin=1
        )

        findings.append(
            Finding(
                analyst_name=ANALYST_NAME,
                cluster=CLUSTER,
                scope_type="system",
                scope_key=SCOPE_KEY,
                signal_json={
                    "edit_id": edit.entry_id,
                    "skill_path": edit.skill_path,
                    "detected_at": edit.detected_at,
                    "outcome_delta_before_after": delta,
                    "win_rate_before": before_mean,
                    "win_rate_after": after_mean,
                },
                evidence_count=len(before) + len(after),
                primary_metric=delta,
                metric_name=METRIC_NAME,
                psi=psi,
                narrative=(
                    f"{edit.skill_path} edit {edit.entry_id} ({edit.detected_at}): "
                    f"win rate {before_mean:.2f} before -> {after_mean:.2f} after"
                ),
            )
        )
    return findings


def seed_reference_config(reflection_store) -> None:
    """Idempotent, same posture as every other analyst's
    seed_reference_config in this service."""
    reflection_store.upsert_reference_config(
        analyst_name=ANALYST_NAME,
        scope_type="system",
        metric_name=METRIC_NAME,
        metric_polarity=POLARITY_LOWER_IS_WORSE,
        reference_window_definition="trailing_20_calibration_entries_before_vs_after_each_edit",
        reason="H (governance): a skill edit that lowers win rate afterward is a bad edit",
        updated_by=ANALYST_NAME,
    )
