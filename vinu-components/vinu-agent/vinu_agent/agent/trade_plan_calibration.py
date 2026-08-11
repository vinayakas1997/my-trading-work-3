"""Calibration Tracker wiring (Phase 8, New-talk-agents/new-thinking/
new-restructure/phases/phase-8-summary-agent-polish/): "has this method
been right over time." Real gap found while implementing: `CalibrationTracker`
(vinu-research/calibration.py) tracks calibration per `artifact_id` (a
specific trade-plan artifact), not per angle name -- there is no per-angle
historical accuracy tracker anywhere in this codebase (confirmed by
reading `calibration.py`, `hypothesis_registry.py`, and every angle's own
storage directly; nothing populates entries keyed by angle name). This
module wires in the REAL capability instead of the plan's assumed one: if
a ticker has an associated trade-plan artifact (Phase 4/5's flow), its
real, trackable calibration history is genuine evidence the Summary Agent
can cite -- not a per-angle trust signal, a per-trade-plan one.

Transport-agnostic per the plan's own requirement: tries the real
in-process path first (`broker/research_link.py`'s `get_strategy_store()`,
the same shared instance `OrderGuard` already uses -- confirmed real and
live today, not blocked on any pending migration), falls back to HTTP
against `research-api` (the same route `vinu-portfolio`'s own
`_fetch_outcome_confidence` already calls) if the in-process path is
unavailable for any reason.
"""

from __future__ import annotations

import logging
from typing import Any

LOG = logging.getLogger(__name__)

# Same threshold CalibrationGate itself uses by default (calibration.py) --
# not re-derived here, just reused so this module's "insufficient data"
# reporting agrees with the gate's own real behavior.
DEFAULT_MIN_WINDOW = 10


def get_trade_plan_calibration(
    artifact_id: str, *, research_api_url: str = "http://localhost:8087", min_window: int = DEFAULT_MIN_WINDOW,
) -> dict[str, Any]:
    """Returns a dict with `n_entries`, `passed`, `reasons`, and
    `source` ("in_process" or "http") so a caller/test can confirm which
    transport actually answered -- both must produce the same real result
    for the same underlying data (03-test.md)."""
    try:
        from vinu_research.forecast_skill import compute_calibration

        from ..broker.research_link import get_strategy_store

        store = get_strategy_store()
        entries = store.get_calibration_entries(artifact_id)
        result = compute_calibration(entries)
        reasons = list(result.reasons)
        if result.n_entries < min_window:
            reasons.append(f"calibration window too small ({result.n_entries} < {min_window})")
        return {
            "artifact_id": artifact_id, "n_entries": result.n_entries,
            "passed": result.passed and result.n_entries >= min_window,
            "reasons": reasons, "source": "in_process",
        }
    except Exception as exc:
        LOG.debug("in-process calibration read failed for %s, falling back to HTTP: %s", artifact_id, exc)

    try:
        import httpx

        resp = httpx.get(
            f"{research_api_url}/research/trade-plan/{artifact_id}/calibration", timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        return {
            "artifact_id": artifact_id, "n_entries": data.get("n_entries", 0),
            "passed": bool(data.get("passed", False)), "reasons": list(data.get("reasons", [])),
            "source": "http",
        }
    except Exception as exc:
        LOG.warning("HTTP calibration read also failed for %s: %s", artifact_id, exc)
        return {
            "artifact_id": artifact_id, "n_entries": 0, "passed": False,
            "reasons": [f"calibration unreachable: {exc}"], "source": "error",
        }
