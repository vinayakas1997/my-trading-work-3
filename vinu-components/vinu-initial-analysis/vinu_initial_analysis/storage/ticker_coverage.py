"""Per-ticker coverage pivot -- Decisions 9 and 11 of
missing-pieces-of-system/new-theory-of-trading/01-planning.md.

Deliberately NOT a new source of truth: every value here is read straight
out of `RunLog`'s existing rows (already the single source of truth for
"which run is current," per that module's own docstring) and reshaped
from long (one row per symbol+angle+run) into the wide, one-row-per-ticker
view a human actually wants to glance at -- ticker, the overall date
range covered, whether models were on, and one column's worth of status
per angle. Nothing is stored twice; this is a read-side pivot, computed
fresh from RunLog on every call, the same way the existing angle-coverage
gate (vinu-agent's ticker_gate.py) computes its own coverage check fresh
each time rather than caching a possibly-stale duplicate.

Decision 11: a missing angle isn't always a gap. An angle tagged
`category: model` while `VINU_MODELS_ENABLED=false`, or one of the
Decision 5 permanently-disabled angles, is CORRECTLY absent -- reporting
that the same way as an angle that genuinely hasn't run yet would make
every models-off ticker look permanently, wrongly incomplete. Every
column is therefore one of three states, not a bare null:
  - "not_required"  -- excluded by current policy; absence is expected
  - "pending"        -- required under current policy, hasn't run yet
  - the angle's real status ("completed"/"error"/...) -- it has run
"""

from __future__ import annotations

from typing import Any

from vinu_infra.system_manifest import resolve_active_angles
from vinu_initial_analysis.storage.meta import RunLog

NOT_REQUIRED = "not_required"
PENDING = "pending"


def build_ticker_coverage(run_log: RunLog, symbol: str, all_angles: list[dict[str, Any]]) -> dict[str, Any]:
    """One row's worth of data for `symbol`.

    `all_angles` is the caller-supplied full angle roster in
    `AngleRunner.list_angles()`'s own shape (each a dict with at least
    `name` and `spec`, the parsed spec.yaml carrying `category`) -- the
    same shape `vinu_infra.system_manifest.resolve_active_angles` already
    consumes, reused here rather than re-deriving the required/not-
    required split a second, possibly-inconsistent way.
    """
    all_angle_names = [a.get("name", "") for a in all_angles]
    required_names = {a.get("name", "") for a in resolve_active_angles(all_angles)}

    runs = run_log.get_runs(symbol=symbol, limit=10_000)

    latest_by_angle: dict[str, dict[str, Any]] = {}
    for row in runs:
        name = row["angle_name"]
        # get_runs() orders newest-first, so the first row seen per angle
        # is already that angle's latest -- no extra sort needed here.
        if name not in latest_by_angle:
            latest_by_angle[name] = row

    angles: dict[str, dict[str, Any] | str] = {}
    for name in all_angle_names:
        row = latest_by_angle.get(name)
        if row is not None:
            # Real data always wins over a policy label: an angle that
            # genuinely ran (e.g. before models were later turned off)
            # keeps showing what actually happened, not "not_required"
            # papering over real history.
            angles[name] = {
                "status": row["status"],
                "analysis_from": row["analysis_from"],
                "analysis_until": row["analysis_until"],
                "policy_version": row["policy_version"],
                "granularity": row["granularity"],
            }
        elif name in required_names:
            angles[name] = PENDING
        else:
            angles[name] = NOT_REQUIRED

    analysis_froms = [r["analysis_from"] for r in runs if r["analysis_from"]]
    analysis_untils = [r["analysis_until"] for r in runs if r["analysis_until"]]

    # "Overall models status" is the most recent run's flag, not an
    # aggregate across every angle -- angles can legitimately be at
    # different ages (one run yesterday, another run last month under a
    # different policy), and the honest single answer to "is this ticker
    # currently under models-on or models-off coverage" is what its
    # single newest run actually saw, not a blend across mismatched runs.
    models_enabled: bool | None = None
    if runs:
        newest = runs[0]
        raw = newest.get("models_enabled")
        models_enabled = None if raw is None else bool(raw)

    has_any_pending = any(v == PENDING for v in angles.values())
    # "completed" requires positive evidence (something has actually run),
    # not merely "nothing is pending" -- a brand-new ticker whose required
    # roster happened to be empty (every angle permanently-disabled or
    # models-off) would otherwise be reported "completed" on day one
    # despite zero real data existing for it.
    overall_status = PENDING if (has_any_pending or not latest_by_angle) else "completed"

    return {
        "ticker": symbol,
        "start_date": min(analysis_froms) if analysis_froms else None,
        "end_date": max(analysis_untils) if analysis_untils else None,
        "models_enabled": models_enabled,
        "angles": angles,
        "angle_count": len(all_angle_names),
        "required_angle_count": len(required_names),
        "angles_with_data": sum(1 for v in angles.values() if isinstance(v, dict)),
        "overall_status": overall_status,
    }
