import json
import logging

from ..agent.tools import BaseTool

LOG = logging.getLogger(__name__)


class GetSignalEvidenceTool(BaseTool):
    name = "get_signal_evidence"
    description = (
        "Read recorded must-condition trigger history for a ticker -- see "
        "missing-pieces-of-system/new-theory-of-trading. Each recorded row is one "
        "historical SMA(5)-crosses-above-SMA(50) event with a full point-in-time "
        "supporting-indicator snapshot (51 indicators: ADX, RSI, the SMA/EMA family, "
        "MACD, Bollinger, Ichimoku, and more) and, once its horizon has elapsed, the "
        "realized forward outcome (max favorable/adverse excursion, return at "
        "horizon). Read-only, backed by the same store the signal_evidence angle's "
        "historical backfill already writes to -- there is no analysis/bucketing "
        "layer yet (Phase 3 is not built), so this returns raw recorded rows plus "
        "honest counts, never a computed win rate or statistic. Pass trigger_id to "
        "fetch one specific event's full indicator snapshot instead of the summary "
        "list for a symbol."
    )
    parameters = {
        "type": "object",
        "properties": {
            "symbol": {
                "type": "string",
                "description": "Filter to this ticker's recorded triggers (optional -- omit to list across all symbols)",
            },
            "trigger_id": {
                "type": "string",
                "description": "Fetch one specific trigger's full indicator snapshot + outcome, instead of the summary list (optional)",
            },
            "limit": {
                "type": "integer",
                "description": "Max triggers to return in the summary list (optional, default 50)",
            },
        },
        "required": [],
    }
    is_readonly = True

    def __init__(self):
        self._services_config = {}

    def execute(self, **kwargs) -> str:
        symbol = kwargs.get("symbol")
        trigger_id = kwargs.get("trigger_id")
        limit = int(kwargs.get("limit") or 50)
        symbol_upper = symbol.upper() if symbol else None

        try:
            from ..broker.research_link import get_signal_evidence_store

            store = get_signal_evidence_store()
            if trigger_id:
                row = store.get_trigger(trigger_id)
                if row is None:
                    return json.dumps({"status": "not_found", "trigger_id": trigger_id})
                return json.dumps({"status": "ok", "trigger": row})
            triggers = store.list_triggers(symbol_upper, limit)
            return json.dumps({
                "status": "ok",
                "symbol": symbol_upper,
                "count": len(triggers),
                "outcomes_recorded": _count_outcomes_recorded(triggers),
                "triggers": triggers,
            })
        except Exception as exc:
            LOG.debug("get_signal_evidence: in-process read failed, falling back to HTTP: %s", exc)

        import httpx
        try:
            from vinu_infra.auth import internal_auth_headers as _iah
            _h = _iah() or None
        except Exception:
            _h = None

        url = self._services_config.get("vinu_research", "http://localhost:8087")

        if trigger_id:
            resp = httpx.get(f"{url}/research/signal-evidence/{trigger_id}", headers=_h, timeout=30)
            if resp.status_code == 404:
                return json.dumps({"status": "not_found", "trigger_id": trigger_id})
            resp.raise_for_status()
            return json.dumps({"status": "ok", "trigger": resp.json()})

        params: dict = {"limit": limit}
        if symbol_upper:
            params["symbol"] = symbol_upper
        resp = httpx.get(f"{url}/research/signal-evidence", params=params, headers=_h, timeout=30)
        resp.raise_for_status()
        body = resp.json()
        triggers = body.get("triggers", [])
        return json.dumps({
            "status": "ok",
            "symbol": symbol_upper,
            "count": body.get("count", len(triggers)),
            "outcomes_recorded": _count_outcomes_recorded(triggers),
            "triggers": triggers,
        })


def _count_outcomes_recorded(triggers: list) -> int:
    return sum(1 for t in triggers if t.get("outcome_recorded_at"))
