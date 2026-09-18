"""Analysis K -- does retrieved memory actually help. Design reference:
missing-pieces-of-system/maturity-agentic-system/thinking-1/02-decided-pattern/
25-A-Y-details/04-decision-process-cognition.md ("K").

Was blocked until 2026-09-19: the prompt-injection path in
`vinu_agent/agent/context.py` only ever formatted facts/memory entries
into the free-text prompt, with no structured record of which
`facts.id`/`memory_entries.id` were actually selected for a given
session. The new writer that closes that gap is
`vinu_agent/storage/injected_context_log.py` (`InjectedContextLogStore`),
written once per `ContextBuilder.build_messages()` call, keyed by
`session_id`. This module is the read+join side: same
`TeamRunStore.get_latest_verdict_by_session_id` join key analysis D
already uses (`decision_process.py`), just joined against "did this
session ever have a fact/memory injected" instead of "did this LLM call
need a retry."

Two independent findings, one per source (facts_registry vs.
unified_memory) -- a session can have one without the other, and they
answer different product questions (is the facts registry worth
maintaining vs. is the memory-recall pipeline worth its token budget).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from vinu_infra.reflection import (
    Finding,
    POLARITY_LOWER_IS_WORSE,
    population_stability_index,
)

from vinu_agent.storage.injected_context_log import InjectedContextLogStore
from vinu_agent.storage.team_runs import TeamRunStore

ANALYST_NAME = "memory_effectiveness"
CLUSTER = "Decision-Process / Cognition"
METRIC_NAME = "verdict_quality_delta"

# Same order-of-magnitude floor as D (decision_process.py) -- a per-source,
# per-cycle two-group comparison this granular needs at least this many
# comparable sessions on each side to mean anything.
MIN_EVIDENCE_COUNT = 30

# Same real verdict strings D already established as the only two "bad
# outcome" values this codebase writes into `team_runs.verdict`.
_REJECTED_VERDICTS = {"STOP", "REJECTED"}

_SOURCES = ("facts_registry", "unified_memory")


def _is_rejected(verdict: str) -> bool:
    return verdict in _REJECTED_VERDICTS


def run(
    data_root_paths: dict[str, Path],
    service_clients: Optional[dict[str, Any]] = None,
) -> list[Finding]:
    """`data_root_paths["vinu_agent"]` must point at a mounted copy of
    vinu-agent's own data root (same mount already used by
    `decision_process.py` for `team_runs.db`/`llm_calls.db`)."""
    data_root = Path(data_root_paths["vinu_agent"])
    context_store = InjectedContextLogStore(data_root / "injected_context_log.db")
    team_store = TeamRunStore(data_root / "team_runs.db")

    # One pass over every session with a resolved verdict, recording
    # whether each source ever injected something for it -- avoids
    # re-querying injected_context_log per source per session.
    had_source: dict[str, dict[str, bool]] = {src: {} for src in _SOURCES}
    quality_by_session: dict[str, float] = {}

    for session_id in team_store.distinct_session_ids_with_verdict():
        verdict = team_store.get_latest_verdict_by_session_id(session_id)
        if verdict is None:
            continue
        quality_by_session[session_id] = 0.0 if _is_rejected(verdict) else 1.0

        context_rows = context_store.list_by_session_id(session_id)
        had_source["facts_registry"][session_id] = any(r.fact_ids for r in context_rows)
        had_source["unified_memory"][session_id] = any(r.memory_ids for r in context_rows)

    findings: list[Finding] = []
    for source in _SOURCES:
        with_labels = [
            quality_by_session[sid] for sid, had in had_source[source].items() if had
        ]
        without_labels = [
            quality_by_session[sid] for sid, had in had_source[source].items() if not had
        ]
        evidence_count = len(with_labels) + len(without_labels)
        if evidence_count < MIN_EVIDENCE_COUNT or not with_labels or not without_labels:
            continue

        verdict_quality_with = sum(with_labels) / len(with_labels)
        verdict_quality_without = sum(without_labels) / len(without_labels)
        delta = verdict_quality_with - verdict_quality_without

        # Reference = sessions with nothing injected (the baseline "no
        # memory available" outcome), current = sessions that had a
        # fact/memory injected -- same anti-circular, recomputed-fresh-
        # every-cycle posture as D.
        psi = population_stability_index(
            without_labels, with_labels, bin_count=2, min_samples_per_bin=1
        )

        findings.append(
            Finding(
                analyst_name=ANALYST_NAME,
                cluster=CLUSTER,
                scope_type="system",
                scope_key=source,
                signal_json={
                    "verdict_quality_with": verdict_quality_with,
                    "verdict_quality_without": verdict_quality_without,
                    "with_evidence_count": len(with_labels),
                    "without_evidence_count": len(without_labels),
                },
                evidence_count=evidence_count,
                primary_metric=delta,
                metric_name=METRIC_NAME,
                psi=psi,
                narrative=(
                    f"{source}: verdict quality {verdict_quality_with:.2f} with vs. "
                    f"{verdict_quality_without:.2f} without"
                ),
            )
        )
    return findings


def seed_reference_config(reflection_store) -> None:
    """Idempotent, same "seed on every worker-cycle start" posture as
    every other analyst here. One row covers both `scope_key` values
    (facts_registry/unified_memory share `metric_name` and polarity;
    `reflection_reference_config` isn't keyed by scope_key at all, same
    as D's single row covering every `role` scope_key)."""
    reflection_store.upsert_reference_config(
        analyst_name=ANALYST_NAME,
        scope_type="system",
        metric_name=METRIC_NAME,
        metric_polarity=POLARITY_LOWER_IS_WORSE,
        reference_window_definition="all_sessions_with_a_resolved_verdict",
        reason="K: a shrinking or negative quality delta means retrieved "
        "context is no longer earning its keep",
        updated_by=ANALYST_NAME,
    )
