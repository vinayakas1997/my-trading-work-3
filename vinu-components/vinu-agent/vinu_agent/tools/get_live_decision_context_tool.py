"""Point 5's tool (reverse-engineering/
05-deciding-agent-and-precondition-tracking.md Part A): composes, in one
call, everything live_decision_agent needs to decide on a (ticker,
strategy) pair that has reached ready_to_execute --

1. The pair's current stage + point 3's persisted live indicator
   snapshot (GET vinu-live's /live/decision-context/{ticker}/{strategy}).
2. The strategy's own precondition claim + must/confirmation conditions
   (GET vinu-strategy's /strategy/strategies/{name}).
3. Historical evidence for this ticker (reuses GetSignalEvidenceTool's
   own execute() rather than re-implementing the in-process/HTTP-
   fallback lookup a second time -- same "reduce, don't rebuild"
   reasoning already applied elsewhere in this design series).
4. This exact (ticker, strategy) pair's own past live-decision verdicts
   (GET vinu-live's /live/decisions/{ticker}/{strategy}) -- so the agent
   can see what it (or a prior run) already decided on earlier
   occurrences of this same setup, not just Track 1's raw trigger/
   outcome rows. Closes the gap where a real, evidence-grounded verdict
   used to be computed once and then discarded (only logged) -- now it's
   both durably recorded (poller.py::_trigger_live_decision) and fed
   back in as real context for the next decision.
5. Track 2 moves for this ticker with no matching Track 1 trigger
   (GET vinu-research's /research/unconfirmed-moves?symbol=) -- the
   `track2_only` case: a real price move no strategy's must-condition
   was watching for. Fails open to [] when the fetch fails, same as
   every other field.

Same BaseTool / in-process-first-then-HTTP-fallback shape as
signal_evidence_tool.py, not a new pattern.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from ..agent.tools import BaseTool
from .signal_evidence_tool import GetSignalEvidenceTool

LOG = logging.getLogger(__name__)

_maturity_consultation_store: Any = None


def _get_maturity_consultation_store() -> Any:
    """Lazily-built module-level singleton, same idiom as every other
    on-disk store in vinu-agent (broker/daily_limits.py,
    broker/symbol_limits.py, ...): one instance per process, path
    resolved from VINU_AGENT_DATA_ROOT the same way every sibling store
    in this package already does."""
    global _maturity_consultation_store
    if _maturity_consultation_store is None:
        from vinu_infra.maturity_consultation import MaturityConsultationStore

        root = os.environ.get("VINU_AGENT_DATA_ROOT", str(Path.home() / ".vinu"))
        _maturity_consultation_store = MaturityConsultationStore(
            str(Path(root) / "maturity_consultations.db"),
        )
    return _maturity_consultation_store


def _filter_to_strategy_conditions(summary: dict, must_conditions: Any) -> dict:
    """Keep only the trigger rows recorded under THIS strategy's own must-conditions (exact names, via the shared
    `condition_names` rule the live poller records under), and recount outcomes on that subset. Otherwise rows
    for other conditions on the same ticker (e.g. the SMA5/50 backfill) make a strategy with no evidence of its
    own look evidenced (features-logic-checking D4). Without a known condition list nothing is filtered, and the
    summary says so; the original counts stay visible as `all_conditions_count`."""
    if summary.get("status") != "ok" or "triggers" not in summary:
        return summary
    if not isinstance(must_conditions, list) or not must_conditions:
        return {**summary, "filtered_to_strategy": False}
    from vinu_infra.condition_names import condition_name

    own = {condition_name(c) for c in must_conditions if isinstance(c, dict)}
    if not own:
        return {**summary, "filtered_to_strategy": False}
    kept = []
    for t in summary["triggers"]:
        names = t.get("must_condition")
        names = {names} if isinstance(names, str) else set(names or [])
        if own <= names:
            kept.append(t)
    return {
        **summary,
        "filtered_to_strategy": True,
        "strategy_conditions": sorted(own),
        "all_conditions_count": summary.get("count", len(summary["triggers"])),
        "count": len(kept),
        "outcomes_recorded": sum(1 for t in kept if t.get("outcome_recorded_at")),
        "triggers": kept,
    }


class GetLiveDecisionContextTool(BaseTool):
    name = "get_live_decision_context"
    description = (
        "Read everything needed to decide on a (ticker, strategy) pair that has reached "
        "ready_to_execute in the live decision loop: its current stage and point-in-time "
        "live indicator snapshot, the strategy's own must-condition/confirmation-condition/ "
        "precondition definition, and historical must-condition trigger evidence for this "
        "ticker (same data get_signal_evidence returns). Read-only -- deciding whether to "
        "execute happens in your own final answer, never here. Honest raw data throughout: "
        "no computed win rate or confidence score, since Phase 3/Layer 4's bucket table "
        "does not exist yet (see reverse-engineering/07-bucket-table-deferred.md). May also "
        "include maturity_status (the system-wide maturity tier: cold_start/paper_only/"
        "early_live/mature, with its real evidence) when that's enabled -- one more honest "
        "input for your own judgment, never a hard gate. Also includes unconfirmed_moves "
        "(Track 2 real price moves with no matching Track 1 trigger -- check whether "
        "Track 2 saw something your strategy missed before EXECUTE; [] means none on file "
        "or the fetch failed) and reflection_notes (currently notable/significant "
        "reflection beliefs across clusters -- advisory system-health notes, e.g. regime "
        "degrading; [] means all routine or the fetch failed). past_closed_trades lists how "
        "earlier EXECUTEs on this ticker and strategy ended (exit reason, entry and exit "
        "price, return before costs); a null return means it was not recorded."
    )
    parameters = {
        "type": "object",
        "properties": {
            "ticker": {"type": "string", "description": "The symbol to check (required)"},
            "strategy_id": {"type": "string", "description": "The strategy name to check (required)"},
        },
        "required": ["ticker", "strategy_id"],
    }
    is_readonly = True
    _config: Any = None

    def __init__(self):
        self._services_config = {}

    def execute(self, **kwargs) -> str:
        ticker = (kwargs.get("ticker") or "").upper()
        strategy_id = kwargs.get("strategy_id") or ""
        if not ticker or not strategy_id:
            return json.dumps({"status": "error", "error": "ticker and strategy_id are required"})

        live_url = self._services_config.get("vinu_live", "http://localhost:8091")
        strategy_url = self._services_config.get("vinu_strategy", "http://localhost:8084")

        decision_context = self._fetch_json(
            f"{live_url}/live/decision-context/{ticker}/{strategy_id}",
        )
        strategy_config = self._fetch_json(
            f"{strategy_url}/strategy/strategies/{strategy_id}",
        )
        past_decisions = self._fetch_json(
            f"{live_url}/live/decisions/{ticker}/{strategy_id}",
        )

        evidence_tool = GetSignalEvidenceTool()
        evidence_tool._services_config = self._services_config
        signal_evidence_summary = json.loads(evidence_tool.execute(symbol=ticker, limit=50))
        signal_evidence_summary = _filter_to_strategy_conditions(
            signal_evidence_summary, strategy_config.get("must_conditions"),
        )

        maturity_status = self._maturity_status_if_enabled(ticker, strategy_id)

        research_url = self._services_config.get("vinu_research", "http://localhost:8087")
        unconfirmed = self._fetch_json(
            f"{research_url}/research/unconfirmed-moves?symbol={ticker}&limit=10",
            edge_id="research.unconfirmed_moves->agent.live_decision_context", non_empty_key="events",
        )

        reflection_url = self._services_config.get("vinu_reflection", "http://localhost:8092")
        notable = self._fetch_json(
            f"{reflection_url}/reflection/beliefs/notable?limit=10",
            edge_id="reflection.notable_beliefs->agent.live_decision_context", non_empty_key="beliefs",
        )

        from vinu_infra.uncertainty import assess_uncertainty

        precondition = strategy_config.get("precondition")
        uncertainty = assess_uncertainty(
            novelty=decision_context.get("novelty"),
            outcomes_recorded=signal_evidence_summary.get("outcomes_recorded"),
            evidence_ok=signal_evidence_summary.get("status") == "ok",
            maturity_tier=(maturity_status or {}).get("tier") if maturity_status else None,
            precondition_tested=precondition.get("tested") if isinstance(precondition, dict) else None,
            live_snapshot_present=bool(decision_context.get("live_snapshot")),
            strategy_config_present=bool(strategy_config),
        )

        return json.dumps({
            "status": "ok",
            "uncertainty": uncertainty,
            "ticker": ticker,
            "strategy_id": strategy_id,
            "stage": decision_context.get("stage"),
            "trigger_id": decision_context.get("trigger_id"),
            "live_snapshot": decision_context.get("live_snapshot", {}),
            "must_conditions": strategy_config.get("must_conditions", []),
            "confirmation_conditions": strategy_config.get("confirmation_conditions", []),
            "precondition": strategy_config.get("precondition", {"description": "", "defined": False, "tested": False}),
            "signal_evidence_summary": signal_evidence_summary,
            "past_live_decisions": past_decisions.get("decisions", []),
            "past_closed_trades": past_decisions.get("closed_positions", []),
            "maturity_status": maturity_status,
            "unconfirmed_moves": unconfirmed.get("events", []),
            "reflection_notes": notable.get("beliefs", []),
        }, indent=2)

    def _maturity_status_if_enabled(self, ticker: str, strategy_id: str) -> dict:
        """high-expectations follow-up, point #3: live_decision_agent
        consults the system-wide maturity tier as one more input to its
        own EXECUTE/SKIP call -- never a hard gate here (this tool is
        read-only; deciding stays in the agent's own final answer, same
        as every other field this tool returns). Opt-in via
        `AgentConfig.live_decision_maturity_scaling_enabled`, off by
        default. `{}` (not present/empty) means either the knob is off or
        the fetch failed -- fails open, same as every other field
        `_fetch_json` already backs."""
        enabled = getattr(self._config, "live_decision_maturity_scaling_enabled", False)
        if not enabled:
            return {}
        research_url = self._services_config.get("vinu_research", "http://localhost:8087")
        status = self._fetch_json(
            f"{research_url}/research/maturity/status", edge_id="maturity.status->agent.live_decision_context",
        )
        store = _get_maturity_consultation_store()
        scope_key = f"{ticker}:{strategy_id}"
        if not status:
            store.record(
                service="vinu-agent", consumer="live_decision", tier="unknown",
                action_taken="no_change_status_unavailable", scope_key=scope_key,
            )
            return {}
        store.record(
            service="vinu-agent", consumer="live_decision", tier=status.get("tier", "unknown"),
            action_taken="context_included", scope_key=scope_key, evidence=status,
        )
        return status

    @staticmethod
    def _fetch_json(url: str, edge_id: str | None = None, non_empty_key: str | None = None) -> dict:
        """GET `url` as JSON; {} on any failure (fail-open, as before). With `edge_id`, the outcome is also recorded
        as a pipeline edge: `received`, `empty` (no body, or `non_empty_key` absent / empty) or `missing` (the request
        failed) -- the tool itself cannot tell a failed read from an empty answer, the recorder can."""
        import httpx
        try:
            from vinu_infra.auth import internal_auth_headers as _iah
            headers = _iah() or None
        except Exception:
            headers = None

        def _rec(status: str, detail: str = "", **kw) -> None:
            if edge_id is None:
                return
            try:
                from vinu_infra.pipeline_edge_recorder import record_edge

                record_edge(edge_id, status, detail, **kw)
            except Exception:  # noqa: BLE001
                pass

        try:
            resp = httpx.get(url, headers=headers, timeout=30)
            resp.raise_for_status()
            body = resp.json()
        except Exception as exc:
            LOG.warning("get_live_decision_context: fetch failed for %s: %s", url, exc)
            _rec("missing", str(exc))
            return {}
        empty = not body or (non_empty_key is not None and isinstance(body, dict) and not body.get(non_empty_key))
        _rec("empty" if empty else "received", payload=body)
        return body
