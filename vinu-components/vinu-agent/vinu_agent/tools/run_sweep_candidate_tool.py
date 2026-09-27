import asyncio
import json
import logging

from ..agent.tools import BaseTool

LOG = logging.getLogger(__name__)

# item #17 finding #4 (system-wide-audit-and-design/
# 02-open-questions-strategy-and-simulation.md): the old hardcoded 180
# here was less than vinu-research's own worst-case retry budget for the
# single simulator call this HTTP fallback triggers server-side --
# tools.py's `_simulator_client` (timeout=120.0, max_retries=3) can
# legitimately take 3 * 120s of attempts plus exponential backoff between
# them (vinu-infra/client.py's `ResilientClient`: `retry_backoff=1.0`,
# `wait = retry_backoff * 2**attempt + random.uniform(0, 1.0)` after
# attempts 0 and 1, capping at (1.0+1.0) + (2.0+1.0) = 5.0s) before
# raising -- 3*120 + 5.0 = 365.0s worst case. A slow-but-alive simulator
# validly exceeding the old 180s wall was read by this file's own except
# Exception (pre-item-#17-finding-#3 fix) as "the whole call failed,"
# silently duplicating an already-in-flight, expensive candidate run --
# exactly the compound retry-storm risk this item names. Set above the
# real worst case, not just bumped by feel, with a fixed margin for the
# HTTP round-trip and server-side work either side of the simulator call
# itself.
_SIMULATOR_WORST_CASE_SEC = 3 * 120.0 + 5.0
_SWEEP_CANDIDATE_TIMEOUT_SEC = _SIMULATOR_WORST_CASE_SEC + 35.0


def _serialize_sweep_candidate(result) -> dict:
    """Exactly routes_sweep.py's own `_serialize` shape."""
    return {
        "run_id": result.run_id,
        "strategy_name": result.strategy_name,
        "strategy_code": result.strategy_code,
        "params_used": result.params_used,
        "metrics": result.metrics,
        "trade_count": result.trade_count,
        "validation": result.validation,
    }


class RunSweepCandidateTool(BaseTool):
    name = "run_sweep_candidate"
    description = (
        "Run ONE backtest of a strategy at ONE specific set of numeric "
        "parameter values (e.g. SMA period=9, RSI threshold=25) and return "
        "the full result including the statistical validation block. This "
        "tool does not decide which values to try or when to stop — that "
        "adaptive reasoning is the caller's job, calling this repeatedly "
        "round by round. Two modes: (1) recipe mode — pass `recipe` (see "
        "list_sweep_recipes) and `params` as a JSON object with the full "
        "parameter set for this candidate. (2) base_code mode — pass "
        "`base_code` (an existing strategy's full source, e.g. from a prior "
        "iteration) plus `param_name`/`param_value` to vary exactly one "
        "already-present numeric parameter in it."
    )
    parameters = {
        "type": "object",
        "properties": {
            "symbol": {"type": "string", "description": "Stock symbol"},
            "from_date": {"type": "string", "description": "Start date YYYY-MM-DD"},
            "to_date": {"type": "string", "description": "End date YYYY-MM-DD"},
            "recipe": {
                "type": "string",
                "description": "Recipe-mode: a built-in strategy template key (see list_sweep_recipes). Requires `params`.",
            },
            "params": {
                "type": "string",
                "description": "Recipe-mode: JSON object of the full parameter set for this candidate, e.g. '{\"fast_period\": 9, \"slow_period\": 40}'",
            },
            "base_code": {
                "type": "string",
                "description": "Base-code-mode: existing strategy source to vary one parameter of. Requires `param_name`/`param_value`.",
            },
            "param_name": {"type": "string", "description": "Base-code-mode: the parameter name to vary"},
            "param_value": {"type": "number", "description": "Base-code-mode: the new value for param_name"},
            "indicators": {
                "type": "string",
                "description": "Comma-separated indicator kinds to make available, e.g. 'sma_20,rsi_14' (optional)",
            },
            "initial_capital": {
                "type": "number",
                "description": "Starting capital for the backtest (optional, defaults to service config)",
            },
        },
        "required": ["symbol", "from_date", "to_date"],
    }
    is_readonly = False

    def __init__(self):
        self._services_config = {}

    def execute(self, **kwargs) -> str:
        indicators = (
            [k.strip().lower() for k in kwargs["indicators"].split(",") if k.strip()]
            if kwargs.get("indicators") else None
        )
        params = json.loads(kwargs["params"]) if kwargs.get("params") else None

        try:
            result = asyncio.run(self._run_in_process(
                symbol=kwargs["symbol"], from_date=kwargs["from_date"], to_date=kwargs["to_date"],
                recipe=kwargs.get("recipe"), params=params, base_code=kwargs.get("base_code"),
                param_name=kwargs.get("param_name"), param_value=kwargs.get("param_value"),
                indicators=indicators, initial_capital=kwargs.get("initial_capital"),
            ))
            return json.dumps(_serialize_sweep_candidate(result))
        except ImportError as exc:
            # item #17 finding #3, the concrete manifestation of this
            # file's own compound retry-storm risk (finding #4 below is
            # this exact HTTP fallback timeout, sitting under a simulator
            # client with its own timeout=120.0/max_retries=3 -- a
            # legitimately slow-but-alive call can validly exceed the old
            # 180s once retries are counted, see _SWEEP_CANDIDATE_
            # TIMEOUT_SEC's own derivation below). Unlike run_research(), nothing
            # in vinu_research.sweep.run_sweep_candidate() catches
            # InfrastructureError from `tools.run_backtest()` -- it was
            # propagating straight into this blanket `except Exception`,
            # which silently re-ran the *entire* candidate over HTTP
            # (hitting the same 180s wall again) instead of surfacing the
            # real "simulator is down/rejecting" failure. Narrowed to
            # ImportError (research_link.py's own documented reason for
            # this fallback: vinu-research not installed in this
            # deployment) so InfrastructureError and any other real
            # failure propagate to ToolRegistry.execute()'s own
            # except Exception, which already turns it into a proper
            # `{"status": "error", ...}` response instead of a silent
            # duplicate run.
            LOG.debug("run_sweep_candidate: vinu-research not importable, falling back to HTTP: %s", exc)

        import httpx
        try:
            from vinu_infra.auth import internal_auth_headers as _iah
            _h = _iah() or None
        except Exception:
            _h = None

        url = self._services_config.get("vinu_research", "http://localhost:8087")
        payload = {
            "symbol": kwargs["symbol"],
            "from_date": kwargs["from_date"],
            "to_date": kwargs["to_date"],
        }
        if kwargs.get("recipe"):
            payload["recipe"] = kwargs["recipe"]
            if params:
                payload["params"] = params
        if kwargs.get("base_code"):
            payload["base_code"] = kwargs["base_code"]
            if kwargs.get("param_name"):
                payload["param_name"] = kwargs["param_name"]
            if kwargs.get("param_value") is not None:
                payload["param_value"] = kwargs["param_value"]
        if indicators:
            payload["indicators"] = indicators
        if kwargs.get("initial_capital") is not None:
            payload["initial_capital"] = kwargs["initial_capital"]

        resp = httpx.post(
            f"{url}/research/sweep/candidate", json=payload, headers=_h,
            timeout=_SWEEP_CANDIDATE_TIMEOUT_SEC,
        )
        resp.raise_for_status()
        return resp.text

    async def _run_in_process(self, **kwargs):
        from vinu_research.sweep import run_sweep_candidate

        from ..broker.research_link import get_research_config, get_research_tools

        tools = get_research_tools(get_research_config())
        try:
            return await run_sweep_candidate(tools=tools, **kwargs)
        finally:
            await tools.close()


class ListSweepRecipesTool(BaseTool):
    name = "list_sweep_recipes"
    description = (
        "List built-in strategy recipes available for run_sweep_candidate's "
        "recipe mode, each with its tunable parameter names and default "
        "values. Read this before picking a recipe + params."
    )
    parameters = {"type": "object", "properties": {}, "required": []}
    is_readonly = True

    def __init__(self):
        self._services_config = {}

    def execute(self, **kwargs) -> str:
        try:
            from vinu_research.generator import list_recipe_details

            return json.dumps({"recipes": list_recipe_details()})
        except Exception as exc:
            LOG.debug("list_sweep_recipes: in-process read failed, falling back to HTTP: %s", exc)

        import httpx
        try:
            from vinu_infra.auth import internal_auth_headers as _iah
            _h = _iah() or None
        except Exception:
            _h = None

        url = self._services_config.get("vinu_research", "http://localhost:8087")
        resp = httpx.get(f"{url}/research/sweep/recipes", headers=_h, timeout=30)
        resp.raise_for_status()
        return resp.text
