from __future__ import annotations

import logging
from typing import Any

import httpx

LOG = logging.getLogger(__name__)


class TradePlanApprovalWorker:
    """Stage 0 (G2a, research-discussion-v1/complete-plan/01-native-gaps.md):
    scans CREATED trade_plan artifacts and calls their approve endpoint --
    the scheduled trigger that was missing, not new gating logic. The gate
    itself lives in vinu-research (trade_plan_authoring.approve_trade_plan),
    fail-closed by design: a fresh plan with no calibration history bootstraps
    off the symbol's own ACTIVE strategy artifact (which already cleared
    meets_promotion_bar()), or is rejected if there's no statistical basis at
    all. This worker only decides *when* to ask, never *whether* to approve --
    same separation ShadowEvaluator keeps from vinu_research.promotion.

    Deliberately HTTP-only, no vinu_research import -- same 3-environment
    isolation boundary TradePlanOrchestrator's own docstring establishes
    (trade plans arrive as plain JSON dicts, never as vinu_research.models
    objects, in this service).
    """

    def __init__(
        self, research_api_url: str = "http://127.0.0.1:8087",
        agent_api_url: str = "http://127.0.0.1:8086",
    ) -> None:
        self._research_api = research_api_url
        # Stage 0 (G2b): where a rejected plan's notify-for-manual-review
        # request goes. Notification failure is deliberately independent of
        # approval outcome -- see _approve_one's try/except around it. No
        # dedup/cooldown yet (every cycle a plan stays rejected, it
        # notifies again) -- that's tracker item A33, Stage A, not this one.
        self._agent_api = agent_api_url
        try:
            from vinu_infra.auth import internal_auth_headers
            _headers = internal_auth_headers() or None
        except Exception:
            _headers = None
        self._http = httpx.AsyncClient(timeout=15.0, headers=_headers)

    async def close(self) -> None:
        await self._http.aclose()

    async def approve_all(self) -> list[dict[str, Any]]:
        """Attempt to approve every CREATED trade_plan artifact. Best-effort
        per artifact -- one rejection/error never blocks the rest of the
        batch, same posture as ShadowEvaluator.evaluate_all()."""
        results: list[dict[str, Any]] = []
        for artifact in await self._list_created_trade_plans():
            results.append(await self._approve_one(artifact))
        return results

    async def _list_created_trade_plans(self) -> list[dict[str, Any]]:
        try:
            resp = await self._http.get(
                f"{self._research_api}/research/artifacts",
                params={"status": "CREATED", "type_": "trade_plan"},
            )
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            LOG.warning("Failed to list CREATED trade plans: %s", e)
        return []

    async def _approve_one(self, artifact: dict[str, Any]) -> dict[str, Any]:
        artifact_id = artifact.get("artifact_id", "unknown")
        name = artifact.get("name", "unknown")
        try:
            resp = await self._http.post(
                f"{self._research_api}/research/trade-plan/{artifact_id}/approve",
            )
        except Exception as e:
            LOG.warning("Approval request failed for %s: %s", artifact_id, e)
            return {"artifact_id": artifact_id, "name": name, "approved": False, "status": "error", "error": str(e)}

        if resp.status_code == 200:
            LOG.info("Approved trade plan %s (%s)", artifact_id, name)
            return {"artifact_id": artifact_id, "name": name, "approved": True, "status": "approved"}

        if resp.status_code == 409:
            # Fail-closed rejection from the gate itself (no calibration
            # history and no ACTIVE strategy artifact to bootstrap from,
            # or calibration failed) -- not an error, just not approved
            # yet. Retried automatically next cycle.
            reasons = []
            try:
                reasons = (resp.json().get("detail") or {}).get("reasons", [])
            except Exception:
                pass
            LOG.info("Trade plan %s not approved: %s", artifact_id, "; ".join(reasons) or "gate rejected")
            await self._notify_pending(artifact_id, artifact, reasons)
            return {"artifact_id": artifact_id, "name": name, "approved": False, "status": "rejected", "reasons": reasons}

        LOG.warning("Unexpected status approving %s: HTTP %d", artifact_id, resp.status_code)
        return {"artifact_id": artifact_id, "name": name, "approved": False, "status": "http_error", "http_status": resp.status_code}

    async def _notify_pending(self, artifact_id: str, artifact: dict[str, Any], reasons: list[str]) -> None:
        """Best-effort push to vinu-agent's configured chat channels so a
        human can `/approve_plan <artifact_id>` to force it through.
        Deliberately never lets a notification failure affect the
        approval result returned by _approve_one -- unrelated concerns."""
        universe = artifact.get("universe") or []
        symbol = universe[0] if universe else ""
        try:
            await self._http.post(
                f"{self._agent_api}/agent/notify/trade-plan-pending",
                json={"artifact_id": artifact_id, "symbol": symbol, "reasons": reasons},
            )
        except Exception as e:
            LOG.debug("Failed to notify channels about pending trade plan %s: %s", artifact_id, e)
