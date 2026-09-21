"""Structural guardrails on an LLM-produced `cluster_digest` -- built
after real testing (`missing-pieces-of-system/angle-comprehension-
hierarchy/03-real-llm-findings-and-guardrails.md`) confirmed two live
models (Qwen3.5-4B and Qwen3.5-9B, both Q4_K_M, real local runs against
`hindsight-llm`) both produce `cluster_digest` output containing
specific, checkable-and-wrong claims: a miscounted angle-coverage total,
and (the 4B run) an angle cited under the wrong one of the 7 fixed
clusters.

Deliberately narrow, on purpose: this does NOT try to verify every
number a cluster's synthesis sentence cites (that needs real NLP/full
re-derivation, not a guardrail). It catches the two specific, cheaply
and deterministically checkable failure modes real testing actually
found: (1) a cluster key or a cited angle name that doesn't match the
real, fixed A-G scheme, and (2) a stated coverage count that disagrees
with the real, deterministic row-count sum. Both are checked against
ground truth Python already has -- the same "pure Python, not LLM
reasoning" discipline `build_angle_digest` already uses for
`angle_digest`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from vinu_agent.tools.angle_clusters import ANGLE_CLUSTERS, ANGLE_TO_CLUSTER


def _angle_mention_pattern(angle_id: str) -> re.Pattern[str]:
    """Matches an angle id however it's likely to appear in prose: the
    raw underscored id itself, or a human-written variant with spaces/
    hyphens instead of underscores (case-insensitive) -- e.g.
    `kalman_filters` also matches "Kalman Filters" or "kalman-filters".

    Built by escaping each underscore-separated part independently and
    joining with a flexible separator -- `re.escape` on the whole string
    doesn't work here since modern Python's `re.escape` no longer
    escapes `_` at all (it's not a regex special character), so a plain
    `.replace("\\_", ...)` on the escaped string never matches.
    """
    parts = [re.escape(p) for p in angle_id.split("_")]
    spaced = "[ _-]+".join(parts)
    return re.compile(rf"\b{spaced}\b", re.IGNORECASE)


_MENTION_PATTERNS: dict[str, re.Pattern[str]] = {
    angle: _angle_mention_pattern(angle) for angle in ANGLE_TO_CLUSTER
}


def find_angle_mentions(text: str) -> set[str]:
    """Real angle ids that appear to be named in a free-text blob."""
    return {angle for angle, pattern in _MENTION_PATTERNS.items() if pattern.search(text)}


@dataclass
class ClusterDigestFinding:
    kind: str  # "unknown_cluster_key" | "cross_cluster_mention"
    cluster_key: str
    detail: str


@dataclass
class ValidationReport:
    cluster_findings: list[ClusterDigestFinding] = field(default_factory=list)
    coverage_stated: int | None = None
    coverage_real: int | None = None
    coverage_mismatch: bool = False

    @property
    def ok(self) -> bool:
        return not self.cluster_findings and not self.coverage_mismatch


def validate_cluster_digest(cluster_digest: dict[str, str]) -> list[ClusterDigestFinding]:
    """Checks a `cluster_digest` dict (as `angle_synthesizer` emits it:
    `{"A": "sentence...", "B": "sentence...", ...}`) against the real,
    fixed A-G scheme. Two things flagged, both real findings from actual
    LLM runs, not hypothetical:

    1. A cluster key that isn't one of the real 7 (A-G) -- the model
       invented a cluster that doesn't exist.
    2. A cluster's own sentence naming an angle that's a real member of
       a *different* cluster -- the real, confirmed failure mode from
       the 9B uneven-data run's 4B counterpart (`kalman_filters`, a real
       Cluster A member, cited inside a Cluster B sentence).
    """
    findings: list[ClusterDigestFinding] = []
    for cluster_key, sentence in cluster_digest.items():
        if cluster_key not in ANGLE_CLUSTERS:
            findings.append(ClusterDigestFinding(
                kind="unknown_cluster_key",
                cluster_key=cluster_key,
                detail=f"'{cluster_key}' is not one of the real clusters A-G",
            ))
            continue
        mentioned = find_angle_mentions(sentence)
        for angle in mentioned:
            real_cluster = ANGLE_TO_CLUSTER[angle]
            if real_cluster != cluster_key:
                findings.append(ClusterDigestFinding(
                    kind="cross_cluster_mention",
                    cluster_key=cluster_key,
                    detail=(
                        f"'{angle}' is cited in cluster {cluster_key}'s sentence, "
                        f"but is a real member of cluster {real_cluster}"
                    ),
                ))
    return findings


def validate_coverage_claim(
    stated_count: int, angle_row_counts: dict[str, int]
) -> tuple[bool, int]:
    """Cross-checks an LLM-stated "N of 28 angles have data" claim
    against the real, deterministic row-count sum -- the same kind of
    confirmed hallucination both the 4B (27/28, real 28/28) and 9B
    (26/28, real 28/28) clean-data runs produced. Returns
    `(matches_real_count, real_count)`; the real count should replace
    the stated one when they disagree, never the other way around."""
    real_count = sum(1 for v in angle_row_counts.values() if v > 0)
    return stated_count == real_count, real_count


def validate(
    cluster_digest: dict[str, str],
    stated_coverage_count: int | None = None,
    angle_row_counts: dict[str, int] | None = None,
) -> ValidationReport:
    report = ValidationReport(cluster_findings=validate_cluster_digest(cluster_digest))
    if stated_coverage_count is not None and angle_row_counts is not None:
        matches, real_count = validate_coverage_claim(stated_coverage_count, angle_row_counts)
        report.coverage_stated = stated_coverage_count
        report.coverage_real = real_count
        report.coverage_mismatch = not matches
    return report
