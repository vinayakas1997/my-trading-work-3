"""high-expectations follow-up, points #2/#3 (00-maturity-agentic-system-
explanation.md's step-3 phasing: "risk_gatekeeper/capital_allocator wiring
... still not started"). `vinu-live` has no in-process bridge to
vinu-research (unlike vinu-portfolio's `research_link.py`), so this talks
to the new `GET /research/maturity/status` HTTP route instead -- the exact
shape the design doc itself proposed for a cross-service caller.

Fail-open on the fetch (same posture as `trade_plan/guards.py::halt_reason`
and every other cross-service check in this file's neighborhood): an
unreachable research-api must never be able to silently tighten or loosen
live risk limits by accident, so a fetch failure returns None and callers
treat that as "no scaling this cycle," not a fallback tier guess.
"""

from __future__ import annotations

import logging
from dataclasses import replace
from typing import Any

from vinu_live.breaker.limits import BreakerLimits

LOG = logging.getLogger(__name__)

# Deliberately different constants from vinu-portfolio's capital-multiplier
# tiers (0.1/0.25/0.5/1.0) -- that scales total capital deployed, this
# scales per-trade risk-limit strictness, a different lever solving a
# different problem. Not derived from anything sharper than "meaningfully
# stricter per tier, never zero" -- a guessed starting constant, same
# posture as every other maturity-tier multiplier in this codebase.
_TIER_SCALE: dict[str, float] = {
    "cold_start": 0.25,
    "paper_only": 0.5,
    "early_live": 0.75,
    "mature": 1.0,
}


async def fetch_maturity_status(http: Any, research_api_url: str) -> dict[str, Any] | None:
    """The current system-wide maturity tier + evidence, or None on any
    failure (unreachable service, non-200, malformed body)."""
    try:
        resp = await http.get(f"{research_api_url}/research/maturity/status")
        if getattr(resp, "status_code", None) != 200:
            return None
        body = resp.json()
        if not isinstance(body, dict) or "tier" not in body:
            return None
        return body
    except Exception as e:  # noqa: BLE001 -- fail-open on any fetch error
        LOG.debug("Maturity status fetch failed, failing open: %s", e)
        return None


def scale_limits_for_tier(limits: BreakerLimits, tier: str) -> BreakerLimits:
    """A proportionally-scaled copy of `limits` for an immature system --
    never the input object mutated, and never below a floor that would
    make trading structurally impossible (at least 1 position, at least
    1.0x leverage) even at the strictest tier."""
    scale = _TIER_SCALE.get(tier, 1.0)
    if scale >= 1.0:
        return limits
    return replace(
        limits,
        max_daily_loss_pct=limits.max_daily_loss_pct * scale,
        max_var_95_pct=limits.max_var_95_pct * scale,
        max_greeks_delta=limits.max_greeks_delta * scale,
        max_greeks_gamma=limits.max_greeks_gamma * scale,
        max_greeks_vega=limits.max_greeks_vega * scale,
        max_position_count=max(1, int(limits.max_position_count * scale)),
        max_cluster_exposure_pct=limits.max_cluster_exposure_pct * scale,
        max_leverage=max(1.0, limits.max_leverage * scale),
    )
