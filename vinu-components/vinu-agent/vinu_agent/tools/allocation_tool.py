"""Deterministic allocation tool for the capital_allocator team.

Phase 2 (New-talk-agents/new-thinking/new-restructure/phases/
phase-2-funding-mechanics/): operates on PEND artifacts (risk_gatekeeper-
approved, awaiting funding) rather than already-ACTIVE ones, and sizes
each via vinu-portfolio's real risk-parity engine (POST /portfolio/
evaluate-batch) instead of the old fixed-fractional/deflated_sharpe rule.
Still read-only/no side effects -- the actual PEND->ACTIVE transition is
applied by agent/capital_allocator_hook.py from the manager's final JSON
answer, same "compute here, mutate from the parsed final answer" split
risk_gatekeeper_hook.py already uses (pillar 8: never an agent tool
performs the real mutation itself).
"""

from __future__ import annotations

import json
import logging
from typing import Any

from ..agent.tools import BaseTool

LOG = logging.getLogger(__name__)


class ComputeAllocationCandidatesTool(BaseTool):
    name = "compute_allocation_candidates"
    description = (
        "Given a list of PEND (risk_gatekeeper-approved, awaiting funding) strategy artifact "
        "ids and a total risk budget, return a deterministic funding decision for each: funded "
        "or not, how much, and why. Sizes via vinu-portfolio's real risk-parity engine "
        "(correlation-aware, computed across the whole batch plus the existing active book at "
        "once), capped at each candidate's risk_gatekeeper-approved size -- never above it."
    )
    parameters = {
        "type": "object",
        "properties": {
            "artifact_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "PEND strategy artifact ids competing for capital",
            },
            "budget": {"type": "number", "description": "total risk budget available, in dollars"},
        },
        "required": ["artifact_ids", "budget"],
    }
    is_readonly = True
    _strategy_store: Any = None
    _ticker_ledger_store: Any = None

    def __init__(self):
        self._services_config = {}

    def _log_skip(self, artifact: Any, event_type: str, text: str) -> None:
        """Best-effort TickerLedger visibility for a PEND item that didn't
        get funded this cycle -- never raises. See 02-guard-rail.md:
        'PEND age must be visible, even without auto-expiry.'"""
        if self._ticker_ledger_store is None:
            return
        try:
            ticker = artifact.universe[0] if artifact.universe else ""
            if ticker:
                self._ticker_ledger_store.add_event(
                    ticker=ticker, stage="capital_allocator", event_type=event_type,
                    text=text, ref_id=artifact.artifact_id, source="watchlist",
                )
        except Exception:
            LOG.exception("failed to write TickerLedger row for %s, continuing without it", artifact.artifact_id)

    def execute(self, **kwargs: Any) -> str:
        artifact_ids = kwargs.get("artifact_ids") or []
        budget = float(kwargs.get("budget", 0.0) or 0.0)

        if self._strategy_store is None:
            return json.dumps({"status": "error", "error": "strategy_store not configured"})
        if budget <= 0:
            return json.dumps({"status": "error", "error": "budget must be positive"})

        from vinu_research.models import ArtifactStatus

        results: list[dict[str, Any]] = []
        candidates: list[Any] = []
        for artifact_id in artifact_ids:
            artifact = self._strategy_store.get_artifact(artifact_id)
            if artifact is None:
                results.append({
                    "artifact_id": artifact_id, "funded": False, "amount": 0.0,
                    "reason": "artifact not found",
                })
                continue
            if artifact.status != ArtifactStatus.PEND:
                results.append({
                    "artifact_id": artifact_id, "funded": False, "amount": 0.0,
                    "reason": f"not PEND (status={artifact.status.value}) -- only artifacts risk_gatekeeper approved and awaiting funding compete here",
                })
                continue
            # Staleness re-check right before funding (Phase 2's guard rail:
            # a cheap re-fetch, not a full risk_gatekeeper re-review) --
            # get_artifact() just above IS that re-fetch, not a cached
            # snapshot from whenever the caller assembled artifact_ids.
            candidates.append(artifact)

        if not candidates:
            return json.dumps({
                "status": "ok", "method": "vinu-portfolio risk-parity, capped at risk_gatekeeper's approved_size",
                "budget": budget, "remaining_unallocated": round(budget, 2), "candidates": results,
            }, indent=2)

        batch_payload = [
            {"artifact_id": a.artifact_id, "name": a.name, "symbol": (a.universe[0] if a.universe else "")}
            for a in candidates
        ]

        import httpx

        url = self._services_config.get("vinu_portfolio", "http://localhost:8090")
        try:
            resp = httpx.post(
                f"{url}/portfolio/evaluate-batch", json={"candidates": batch_payload}, timeout=30
            )
            resp.raise_for_status()
            portfolio_result = resp.json()
        except Exception as exc:
            # Fail-closed, never fall back to the old fixed-fraction math --
            # see 02-guard-rail.md: a silent fallback would defeat the
            # entire point of this phase. The whole PEND batch simply waits
            # for the next cadence attempt (nothing here mutates anything).
            LOG.warning("vinu-portfolio unreachable, funding skipped this cycle: %s", exc)
            for a in candidates:
                self._log_skip(a, "funding_skipped_unreachable", f"vinu-portfolio unreachable this cycle: {exc}")
            return json.dumps({
                "status": "error",
                "error": f"vinu-portfolio unreachable, funding skipped this cycle (not a fallback to fixed-fraction math): {exc}",
            })

        if portfolio_result.get("status") not in ("ok", "empty"):
            return json.dumps({
                "status": "error",
                "error": f"vinu-portfolio returned unexpected status {portfolio_result.get('status')!r}",
            })

        weights_by_id = {
            w.get("artifact_id"): w for w in portfolio_result.get("weights", []) if w.get("artifact_id")
        }

        funded_total = 0.0
        for a in candidates:
            weight_entry = weights_by_id.get(a.artifact_id)
            if weight_entry is None:
                results.append({
                    "artifact_id": a.artifact_id, "funded": False, "amount": 0.0,
                    "reason": "not present in vinu-portfolio's evaluated weights",
                })
                self._log_skip(a, "funding_skipped", "not present in vinu-portfolio's evaluated weights")
                continue

            target_weight = float(weight_entry.get("target_weight", 0.0))
            portfolio_computed_size = target_weight * budget
            # Never above what risk_gatekeeper actually approved for this
            # specific candidate -- vinu-portfolio's job is sizing DOWN for
            # real collective constraints, not a second, independent
            # approval that could expand exposure. See 02-guard-rail.md.
            capped_amount = min(a.approved_size, portfolio_computed_size)

            if capped_amount <= 0:
                results.append({
                    "artifact_id": a.artifact_id, "funded": False, "amount": 0.0,
                    "reason": (
                        f"vinu-portfolio weight {target_weight:.4f} x budget {budget:.2f} = "
                        f"{portfolio_computed_size:.2f}, capped at approved_size {a.approved_size:.2f} "
                        f"-> non-positive fundable amount"
                    ),
                })
                self._log_skip(
                    a, "funding_skipped",
                    f"computed size {portfolio_computed_size:.2f} capped by approved_size {a.approved_size:.2f} -> non-positive",
                )
                continue

            amount = round(capped_amount, 2)
            funded_total += amount
            results.append({
                "artifact_id": a.artifact_id, "funded": True, "amount": amount,
                "reason": (
                    f"vinu-portfolio weight {target_weight:.4f} x budget {budget:.2f} = "
                    f"{portfolio_computed_size:.2f}, capped at risk_gatekeeper-approved "
                    f"{a.approved_size:.2f} -> funded {amount:.2f}"
                ),
            })

        return json.dumps({
            "status": "ok",
            "method": "vinu-portfolio risk-parity, capped at risk_gatekeeper's approved_size",
            "budget": budget,
            "remaining_unallocated": round(budget - funded_total, 2),
            "candidates": results,
        }, indent=2)
