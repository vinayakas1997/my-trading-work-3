"""One read-only answer to "how much do we not know?" (v2 B2).

A pure function over inputs the live-decision path already has. It adds no gate and changes no size: it only states a
level (low | medium | high), the reasons, and the inputs that were missing, so "I don't know because inputs were
missing" is distinguishable from "I know and I am neutral". Points per factor are listed in POINTS; level cut-offs
in `level_for`. Never raises on odd input.
"""

from __future__ import annotations

from typing import Any

MIN_OUTCOMES = 20
POINTS = {
    "novelty_high": 2,
    "no_recorded_outcomes": 2,
    "few_recorded_outcomes": 1,
    "maturity_not_mature": 1,
    "precondition_untested": 1,
    "live_snapshot_missing": 2,
    "evidence_unavailable": 2,
    "strategy_config_missing": 1,
}


def level_for(points: int) -> str:
    return "low" if points <= 1 else ("medium" if points <= 3 else "high")


def assess_uncertainty(
    *, novelty: dict[str, Any] | None = None, outcomes_recorded: int | None = None, evidence_ok: bool = True,
    maturity_tier: str | None = None, precondition_tested: bool | None = None,
    live_snapshot_present: bool = True, strategy_config_present: bool = True,
) -> dict[str, Any]:
    reasons: list[str] = []
    missing: list[str] = []

    if not live_snapshot_present:
        missing.append("live_snapshot"); reasons.append("live_snapshot_missing")
    if not strategy_config_present:
        missing.append("strategy_config"); reasons.append("strategy_config_missing")
    if not evidence_ok:
        missing.append("signal_evidence"); reasons.append("evidence_unavailable")
    elif outcomes_recorded is not None:
        if outcomes_recorded <= 0:
            reasons.append("no_recorded_outcomes")
        elif outcomes_recorded < MIN_OUTCOMES:
            reasons.append("few_recorded_outcomes")
    if novelty and novelty.get("novelty_high"):
        reasons.append("novelty_high")
    elif not novelty or novelty.get("status") != "ok":
        missing.append("novelty")                    # unknown, listed but not scored: the check is opt-in
    if maturity_tier is not None and maturity_tier != "mature":
        reasons.append("maturity_not_mature")
    if precondition_tested is False:
        reasons.append("precondition_untested")
    points = sum(POINTS[r] for r in reasons)
    return {"level": level_for(points), "points": points, "reasons": reasons, "missing_inputs": missing}
