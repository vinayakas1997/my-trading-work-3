"""Layer 0 (`reflection_findings_history` / `reflection_beliefs` /
`reflection_reference_config`) and Layer 1 (`classify_severity` /
`compute_trend`, PSI) for the maturity-agentic reflection system.

Design reference: missing-pieces-of-system/maturity-agentic-system/
thinking-1/02-decided-pattern/{01-table-schemas,02-analyst-interface,
03-severity-and-trend,04-reference-baseline-config}.md. This is the
first real implementation of that design -- those docs were "design
only" until now.

Every one of the (eventually) 6 analysts builds `Finding`s and calls
`write_finding()`; nothing else touches these tables directly.
"""

from __future__ import annotations

import json
import math
import time
import uuid
from dataclasses import dataclass
from typing import Any, Optional

from vinu_infra.sqlite import SQLiteBackend

SCOPE_TYPES = ("system", "ticker", "ticker_pair", "strategy_family", "angle")

SEVERITY_ROUTINE = "routine"
SEVERITY_NOTABLE = "notable"
SEVERITY_SIGNIFICANT = "significant"

TREND_IMPROVING = "improving"
TREND_STABLE = "stable"
TREND_DEGRADING = "degrading"

POLARITY_HIGHER_IS_WORSE = "higher_is_worse"
POLARITY_LOWER_IS_WORSE = "lower_is_worse"

_PSI_NOTABLE = 0.1
_PSI_SIGNIFICANT = 0.25

# Same dead-band number as classify_severity's PSI<0.1 "stable" cutoff --
# see compute_trend()'s docstring for why this is a relative-change dead
# band, not a literal PSI (PSI is undefined between two single scalars).
_TREND_DEAD_BAND = 0.1


def _now_ts() -> float:
    return time.time()


def _new_id() -> str:
    return uuid.uuid4().hex[:16]


# ---------------------------------------------------------------------------
# PSI
# ---------------------------------------------------------------------------


def _equi_quantile_edges(reference_values: list[float], bin_count: int) -> list[float]:
    """Bin edges computed once from the reference window, per
    04-reference-baseline-config.md's "fixed from baseline" rule --
    caller is responsible for reusing the same edges across cycles
    rather than recomputing them each time."""
    ordered = sorted(reference_values)
    n = len(ordered)
    edges = []
    for i in range(1, bin_count):
        idx = min(n - 1, max(0, round(i * n / bin_count) - 1))
        edges.append(ordered[idx])
    return edges


def _bucket_proportions(values: list[float], edges: list[float]) -> list[float]:
    n = len(values)
    if n == 0:
        return [0.0] * (len(edges) + 1)
    counts = [0] * (len(edges) + 1)
    for v in values:
        bucket = 0
        while bucket < len(edges) and v > edges[bucket]:
            bucket += 1
        counts[bucket] += 1
    return [c / n for c in counts]


def population_stability_index(
    reference_values: list[float],
    current_values: list[float],
    *,
    bin_count: Optional[int] = None,
    min_samples_per_bin: int = 20,
    epsilon: float = 0.01,
) -> float:
    """PSI = sum((actual% - expected%) * ln(actual% / expected%)), bucketed
    by equi-quantile bins over `reference_values`. Non-negative by
    construction -- magnitude only, no direction (see
    04-reference-baseline-config.md's "Polarity" section).

    `bin_count`: per 04-reference-baseline-config.md's "Bin count" rule,
    `min(20, evidence_count / min_samples_per_bin)` when not given
    explicitly, floored at 2 (a single bucket can't show drift).

    Empty inputs return 0.0 (no evidence, no claimed shift) rather than
    raising -- callers gate on `evidence_count` separately before this is
    ever meaningful.

    Zero-variance reference (every value identical -- common for small,
    near-binary samples, e.g. a tight run of all-correct calibration
    entries) is handled as a special case, not run through equi-quantile
    binning: every quantile of a constant array equals that same
    constant, so a bin edge derived from it cannot tell "current also
    equals the reference value" apart from "current is nothing like the
    reference value" -- both fall on the same side of the one edge that
    exists. 04-reference-baseline-config.md's own "Bin count" section
    anticipates exactly this ("should skip PSI's binned form and use a
    plain two-sample comparison" for degenerate/low-volume cases) --
    implemented here as the fraction of `current_values` that differ
    from the reference's single value, which is 0.0 (no shift) when
    every current value also matches it and rises toward 1.0 as more of
    the current sample departs from it, keeping the same "0 = no shift"
    scale and non-negativity real PSI has, so `classify_severity`'s
    thresholds still apply unchanged."""
    if not reference_values or not current_values:
        return 0.0
    if len(set(reference_values)) < 2:
        ref_value = reference_values[0]
        return sum(1 for v in current_values if v != ref_value) / len(current_values)
    if bin_count is None:
        bin_count = max(2, min(20, len(reference_values) // min_samples_per_bin))
    bin_count = max(1, bin_count)
    edges = _equi_quantile_edges(reference_values, bin_count)
    ref_props = _bucket_proportions(reference_values, edges)
    cur_props = _bucket_proportions(current_values, edges)
    psi = 0.0
    for r, c in zip(ref_props, cur_props):
        r_s, c_s = r + epsilon, c + epsilon
        psi += (c_s - r_s) * math.log(c_s / r_s)
    return psi


def pearson_correlation(xs: list[float], ys: list[float]) -> float:
    """Standard Pearson product-moment correlation coefficient, in
    [-1, 1]. First real user: V (`02-regime-risk-coverage.md`'s
    paper-vs-live performance predictor) -- nothing in this codebase
    computed a correlation coefficient before it.

    Returns 0.0 (no claimed relationship) for degenerate inputs -- fewer
    than 2 paired observations, or either series has zero variance, which
    would make the coefficient undefined (division by zero) -- rather
    than raising. Same "no evidence, no claim" posture
    `population_stability_index`'s own empty-input handling uses. Callers
    gate on their own minimum-sample floor separately before this is ever
    meaningful, same convention as every other cross-analyst metric here.
    """
    n = min(len(xs), len(ys))
    if n < 2:
        return 0.0
    xs, ys = xs[:n], ys[:n]
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    covariance = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    var_x = sum((x - mean_x) ** 2 for x in xs)
    var_y = sum((y - mean_y) ** 2 for y in ys)
    if var_x == 0 or var_y == 0:
        return 0.0
    return covariance / math.sqrt(var_x * var_y)


def classify_severity(psi: float, *, domain_floor_breached: bool = False) -> Optional[str]:
    """`03-severity-and-trend.md`'s three-way split. Returns None for
    `routine` (PSI < 0.1, matching the design's own "most cycles produce
    nothing" rule -- routine is a state, never a written row), else
    `notable` or `significant`. `domain_floor_breached` is the same
    absolute-domain-floor exception `00-index.md` already allows (e.g.
    analysis A's Brier score >= 0.5) -- forces `significant` regardless
    of PSI, since a domain-floor breach shouldn't need a large enough
    reference window to also register as a PSI shift."""
    if domain_floor_breached:
        return SEVERITY_SIGNIFICANT
    if psi < _PSI_NOTABLE:
        return None
    if psi <= _PSI_SIGNIFICANT:
        return SEVERITY_NOTABLE
    return SEVERITY_SIGNIFICANT


def compute_trend(prior_metric: Optional[float], new_metric: float, polarity: str) -> str:
    """`03-severity-and-trend.md` calls for "the same PSI-derived dead-band"
    between the prior and new `primary_metric`. PSI itself is undefined
    over a single before/after scalar pair (it needs a bucketed
    distribution on each side) -- so this reuses the same 0.1 dead-band
    *number* as a relative-change threshold instead, which is the
    closest literal reading that's actually computable from two floats.
    Documented here rather than left implicit, since the design doc
    doesn't spell out this degenerate case.

    No prior row (first-ever finding for this scope) -> `stable`, same
    as the "no reference distribution yet" reasoning `classify_severity`
    uses for empty inputs."""
    if prior_metric is None:
        return TREND_STABLE
    if prior_metric == 0:
        rel_change = 0.0 if new_metric == 0 else 1.0
    else:
        rel_change = abs(new_metric - prior_metric) / abs(prior_metric)
    if rel_change < _TREND_DEAD_BAND:
        return TREND_STABLE
    moved_up = new_metric > prior_metric
    degrading = moved_up if polarity == POLARITY_HIGHER_IS_WORSE else not moved_up
    return TREND_DEGRADING if degrading else TREND_IMPROVING


# ---------------------------------------------------------------------------
# Finding -- the shape every analyst returns from run()
# ---------------------------------------------------------------------------


@dataclass
class Finding:
    analyst_name: str
    cluster: str
    scope_type: str  # system | ticker | ticker_pair | strategy_family | angle
    scope_key: str
    signal_json: dict[str, Any]
    evidence_count: int
    primary_metric: float
    metric_name: str  # keys reflection_reference_config's polarity lookup
    # for `trend` -- e.g. "retry_rejection_delta" for D. Not in the
    # original 02-analyst-interface.md sketch of Finding; added because
    # write_finding() genuinely needs it and the analyst is the only
    # place that knows it.
    psi: float  # the PSI distance the analyst's own Condition already
    # computed (reference vs. this cycle's raw source values) -- reused
    # directly for severity, never recomputed here. See
    # 02-analyst-interface.md's Finding dataclass.
    narrative: Optional[str] = None
    domain_floor_breached: bool = False


# ---------------------------------------------------------------------------
# Layer 0 store
# ---------------------------------------------------------------------------

SCHEMA = """
CREATE TABLE IF NOT EXISTS reflection_findings_history (
    finding_id     TEXT PRIMARY KEY,
    analyst_name   TEXT NOT NULL,
    cluster        TEXT NOT NULL,
    scope_type     TEXT NOT NULL,
    scope_key      TEXT NOT NULL,
    computed_at    REAL NOT NULL,
    signal_json    TEXT NOT NULL DEFAULT '{}',
    evidence_count INTEGER NOT NULL DEFAULT 0,
    severity       TEXT NOT NULL,
    narrative      TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_reflection_findings_scope
    ON reflection_findings_history(analyst_name, scope_type, scope_key);
CREATE INDEX IF NOT EXISTS idx_reflection_findings_computed_at
    ON reflection_findings_history(computed_at);

CREATE TABLE IF NOT EXISTS reflection_beliefs (
    analyst_name   TEXT NOT NULL,
    scope_type     TEXT NOT NULL,
    scope_key      TEXT NOT NULL,
    computed_at    REAL NOT NULL,
    signal_json    TEXT NOT NULL DEFAULT '{}',
    evidence_count INTEGER NOT NULL DEFAULT 0,
    severity       TEXT NOT NULL,
    narrative      TEXT NOT NULL DEFAULT '',
    trend          TEXT NOT NULL,
    primary_metric REAL NOT NULL DEFAULT 0.0,
    PRIMARY KEY (analyst_name, scope_type, scope_key)
);

CREATE TABLE IF NOT EXISTS reflection_reference_config (
    analyst_name                 TEXT NOT NULL,
    scope_type                   TEXT NOT NULL,
    metric_name                  TEXT NOT NULL,
    reference_window_definition  TEXT NOT NULL DEFAULT '',
    bin_count                    INTEGER,
    min_samples_per_bin          INTEGER NOT NULL DEFAULT 20,
    epsilon                      REAL NOT NULL DEFAULT 0.01,
    metric_polarity              TEXT NOT NULL,
    updated_at                   REAL NOT NULL,
    updated_by                   TEXT NOT NULL DEFAULT '',
    reason                       TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (analyst_name, scope_type, metric_name)
);
"""

SCHEMA_VERSION = 1
MIGRATIONS: list[tuple[str, str]] = []


class ReflectionStore(SQLiteBackend):
    SCHEMA = SCHEMA
    SCHEMA_VERSION = SCHEMA_VERSION
    MIGRATIONS = MIGRATIONS

    # -- reference config -------------------------------------------------

    def upsert_reference_config(
        self,
        *,
        analyst_name: str,
        scope_type: str,
        metric_name: str,
        metric_polarity: str,
        reference_window_definition: str = "",
        bin_count: Optional[int] = None,
        min_samples_per_bin: int = 20,
        epsilon: float = 0.01,
        updated_by: str = "",
        reason: str = "",
    ) -> None:
        """Idempotent upsert -- same "seed on every start, never clobber an
        operator's own edit to the same key" posture as
        `vinu-screener seed-default`; each analyst module calls this once
        for its own metric(s) so the row always exists before that
        analyst's first `compute_trend()` call needs `metric_polarity`."""
        self.upsert(
            "reflection_reference_config",
            {
                "analyst_name": analyst_name,
                "scope_type": scope_type,
                "metric_name": metric_name,
                "reference_window_definition": reference_window_definition,
                "bin_count": bin_count,
                "min_samples_per_bin": min_samples_per_bin,
                "epsilon": epsilon,
                "metric_polarity": metric_polarity,
                "updated_at": _now_ts(),
                "updated_by": updated_by,
                "reason": reason,
            },
            conflict_columns=["analyst_name", "scope_type", "metric_name"],
        )

    def get_reference_config(
        self, analyst_name: str, scope_type: str, metric_name: str
    ) -> Optional[dict[str, Any]]:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM reflection_reference_config "
            "WHERE analyst_name = ? AND scope_type = ? AND metric_name = ?",
            (analyst_name, scope_type, metric_name),
        ).fetchone()
        return dict(row) if row is not None else None

    # -- beliefs ------------------------------------------------------------

    def get_belief(
        self, analyst_name: str, scope_type: str, scope_key: str
    ) -> Optional[dict[str, Any]]:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM reflection_beliefs "
            "WHERE analyst_name = ? AND scope_type = ? AND scope_key = ?",
            (analyst_name, scope_type, scope_key),
        ).fetchone()
        return dict(row) if row is not None else None

    def list_beliefs(self, analyst_name: Optional[str] = None) -> list[dict[str, Any]]:
        conn = self._get_conn()
        if analyst_name:
            rows = conn.execute(
                "SELECT * FROM reflection_beliefs WHERE analyst_name = ? "
                "ORDER BY computed_at DESC",
                (analyst_name,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM reflection_beliefs ORDER BY computed_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def list_findings(
        self, analyst_name: Optional[str] = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        conn = self._get_conn()
        if analyst_name:
            rows = conn.execute(
                "SELECT * FROM reflection_findings_history WHERE analyst_name = ? "
                "ORDER BY computed_at DESC LIMIT ?",
                (analyst_name, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM reflection_findings_history ORDER BY computed_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]


def write_finding(store: ReflectionStore, finding: Finding) -> Optional[str]:
    """The one shared write path every analyst funnels through --
    `classify_severity()` + `compute_trend()`, then upserts both tables.
    Returns None (and writes nothing) when severity classifies as
    `routine` -- most cycles, most scopes, write nothing, per
    01-table-schemas.md. Returns the new `finding_id` otherwise.

    `finding.metric_name` keys the `reflection_reference_config` lookup
    used for `trend`'s polarity -- callers must have called
    `upsert_reference_config()` for this (analyst_name, scope_type,
    metric_name) at least once (analyst modules do this idempotently on
    every run, see `ReflectionStore.upsert_reference_config`'s
    docstring). Missing config makes `trend` fall back to `stable`
    (matches `compute_trend`'s own "no data" posture) rather than
    raising -- a misconfigured analyst shouldn't be able to crash the
    worker loop for every other analyst (05-to-do.md's failure-isolation
    requirement).
    """
    severity = classify_severity(finding.psi, domain_floor_breached=finding.domain_floor_breached)
    if severity is None:
        return None

    prior = store.get_belief(finding.analyst_name, finding.scope_type, finding.scope_key)
    prior_metric = prior["primary_metric"] if prior is not None else None

    ref_config = store.get_reference_config(
        finding.analyst_name, finding.scope_type, finding.metric_name
    )
    polarity = ref_config["metric_polarity"] if ref_config else POLARITY_HIGHER_IS_WORSE
    trend = compute_trend(prior_metric, finding.primary_metric, polarity)

    finding_id = _new_id()
    now = _now_ts()
    signal_json_str = json.dumps(finding.signal_json)

    store.upsert(
        "reflection_findings_history",
        {
            "finding_id": finding_id,
            "analyst_name": finding.analyst_name,
            "cluster": finding.cluster,
            "scope_type": finding.scope_type,
            "scope_key": finding.scope_key,
            "computed_at": now,
            "signal_json": signal_json_str,
            "evidence_count": finding.evidence_count,
            "severity": severity,
            "narrative": finding.narrative or "",
        },
        conflict_columns=["finding_id"],
    )
    store.upsert(
        "reflection_beliefs",
        {
            "analyst_name": finding.analyst_name,
            "scope_type": finding.scope_type,
            "scope_key": finding.scope_key,
            "computed_at": now,
            "signal_json": signal_json_str,
            "evidence_count": finding.evidence_count,
            "severity": severity,
            "narrative": finding.narrative or "",
            "trend": trend,
            "primary_metric": finding.primary_metric,
        },
        conflict_columns=["analyst_name", "scope_type", "scope_key"],
    )
    return finding_id


def write_findings(store: ReflectionStore, findings: list[Finding]) -> list[str]:
    """Loops `write_finding()` over one analyst's returned findings for
    one cycle -- what `reflection_worker_main`'s loop calls
    (02-analyst-interface.md). Returns only the ids that were actually
    written (routine findings are silently skipped, not an error)."""
    written = []
    for finding in findings:
        finding_id = write_finding(store, finding)
        if finding_id is not None:
            written.append(finding_id)
    return written
