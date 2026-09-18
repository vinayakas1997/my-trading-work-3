"""Analysis D -- LLM call-quality vs. outcomes. Per-role comparison of
downstream verdict rejection rates for calls that needed a retry vs. calls
that didn't. Design reference:
missing-pieces-of-system/maturity-agentic-system/thinking-1/02-decided-pattern/
25-A-Y-details/04-decision-process-cognition.md ("D").

Both source stores (`llm_calls.db`, `team_runs.db`) are already fully
written by every real call/run in vinu-agent -- this is a pure read +
join, no new writer needed anywhere, which is exactly why D is the
recommended first analyst to build (05-to-do.md). Reads them in-process
via vinu-agent's own storage classes (`LlmCallLogStore`/`TeamRunStore`),
pointed at a mounted copy of vinu-agent's data root -- same
mount-and-import posture as `vinu-agent/broker/research_link.py`'s own
link to vinu-research, not an HTTP call.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from vinu_infra.reflection import (
    Finding,
    POLARITY_HIGHER_IS_WORSE,
    population_stability_index,
)

from vinu_agent.storage.llm_calls import LlmCallLogStore
from vinu_agent.storage.team_runs import TeamRunStore

ANALYST_NAME = "decision_process"
CLUSTER = "Decision-Process / Cognition"
METRIC_NAME = "retry_rejection_delta"

# "a minimum sample (e.g. 30 calls)" -- 04-decision-process-cognition.md's
# own placeholder number, validated as the right order of magnitude by
# 03-severity-and-trend.md's cited drift-detection literature (~100-180
# observations for a *window*; 30 is the right floor for a per-role,
# per-cycle comparison this granular).
MIN_EVIDENCE_COUNT = 30

# Real verdict strings this codebase actually writes into
# `team_runs.verdict` (vinu_agent/agent/team.py's `_extract_verdict`,
# vinu_agent/agent/risk_gatekeeper_hook.py) -- STOP/REJECTED both mean
# "this run was turned away," the only two "bad outcome" values that
# exist today.
_REJECTED_VERDICTS = {"STOP", "REJECTED"}


def _is_rejected(verdict: str) -> bool:
    return verdict in _REJECTED_VERDICTS


def run(
    data_root_paths: dict[str, Path],
    service_clients: Optional[dict[str, Any]] = None,
) -> list[Finding]:
    """`data_root_paths["vinu_agent"]` must point at a mounted copy of
    vinu-agent's own data root (docker-compose.yml mounts
    `./data/agent` read-only into this service at `/agent-data`) -- not
    this service's own `data_root`."""
    data_root = Path(data_root_paths["vinu_agent"])
    llm_store = LlmCallLogStore(data_root / "llm_calls.db")
    team_store = TeamRunStore(data_root / "team_runs.db")

    findings: list[Finding] = []
    for role in llm_store.distinct_roles():
        calls = llm_store.list_calls(role=role, limit=100_000)

        retry_labels: list[float] = []
        no_retry_labels: list[float] = []
        for call in calls:
            if not call.session_id:
                continue
            verdict = team_store.get_latest_verdict_by_session_id(call.session_id)
            if verdict is None:
                continue
            label = 1.0 if _is_rejected(verdict) else 0.0
            (retry_labels if call.retry_count > 0 else no_retry_labels).append(label)

        evidence_count = len(retry_labels) + len(no_retry_labels)
        if evidence_count < MIN_EVIDENCE_COUNT or not retry_labels or not no_retry_labels:
            continue

        retry_reject_rate = sum(retry_labels) / len(retry_labels)
        no_retry_reject_rate = sum(no_retry_labels) / len(no_retry_labels)
        delta = retry_reject_rate - no_retry_reject_rate

        # Reference = no-retry calls' own reject/approve split, current =
        # retry calls' -- a real, non-circular two-group PSI comparison
        # computed fresh from the raw source tables every cycle, never
        # against this analyst's own prior findings (05-to-do.md #3's
        # anti-circularity rule).
        psi = population_stability_index(
            no_retry_labels, retry_labels, bin_count=2, min_samples_per_bin=1
        )

        findings.append(
            Finding(
                analyst_name=ANALYST_NAME,
                cluster=CLUSTER,
                scope_type="system",
                scope_key=role,
                signal_json={
                    "retry_rejection_delta": delta,
                    "retry_reject_rate": retry_reject_rate,
                    "no_retry_reject_rate": no_retry_reject_rate,
                    "retry_evidence_count": len(retry_labels),
                    "no_retry_evidence_count": len(no_retry_labels),
                },
                evidence_count=evidence_count,
                primary_metric=delta,
                metric_name=METRIC_NAME,
                psi=psi,
                narrative=(
                    f"{role}: retry reject-rate {retry_reject_rate:.2f} vs. "
                    f"no-retry {no_retry_reject_rate:.2f}"
                ),
            )
        )
    return findings


def seed_reference_config(reflection_store) -> None:
    """Idempotent, same "seed on every worker-cycle start" posture as
    `vinu-screener seed-default` -- ensures `write_finding()`'s
    `trend` computation always has a polarity to read for this
    analyst's metric, without a separate migration/deploy step."""
    reflection_store.upsert_reference_config(
        analyst_name=ANALYST_NAME,
        scope_type="system",
        metric_name=METRIC_NAME,
        metric_polarity=POLARITY_HIGHER_IS_WORSE,
        reference_window_definition="all_llm_calls_with_a_resolved_verdict",
        reason="D: retries more strongly coupled to bad downstream verdicts",
        updated_by=ANALYST_NAME,
    )
