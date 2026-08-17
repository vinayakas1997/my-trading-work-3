import asyncio
import json
import logging

from ..agent.tools import BaseTool

LOG = logging.getLogger(__name__)


def _serialize_sweep_grid(result) -> dict:
    """Exactly routes_sweep.py's own `_serialize_grid` shape."""
    return {
        "requested": result.requested,
        "succeeded": result.succeeded,
        "completeness": result.completeness,
        "pbo": result.pbo,
        "walk_forward": result.walk_forward,
        "ranked": [
            {
                "params": r.params,
                "score": r.score,
                "risk_score": r.risk_score,
                "complexity_score": r.complexity_score,
                "run_id": r.sweep_result.run_id,
                "strategy_code": r.sweep_result.strategy_code,
                "metrics": r.sweep_result.metrics,
                "trade_count": r.sweep_result.trade_count,
            }
            for r in result.ranked
        ],
        "failed_points": [
            {"params": o.params, "error": o.error} for o in result.outcomes if not o.succeeded
        ],
    }


class RunParameterSweepTool(BaseTool):
    name = "run_parameter_sweep"
    description = (
        "Run a WHOLE grid of strategy parameter combinations in ONE call "
        "and get back a ranked table plus an overfitting estimate (PBO) -- "
        "the recipe-first replacement for hand-writing generate_weights "
        "code point by point. Two modes: (1) recipe mode -- pass `recipe` "
        "(see list_sweep_recipes) and `param_grid` as a JSON array where "
        "each element is a full parameter dict for one candidate, e.g. "
        "'[{\"fast_period\": 5, \"slow_period\": 40}, {\"fast_period\": 10, "
        "\"slow_period\": 40}]'. (2) base_code mode -- pass `base_code` "
        "(an existing strategy's full source) and `param_name`, with "
        "`param_grid` as a JSON array of dicts each containing that one "
        "key, e.g. '[{\"fast_period\": 5}, {\"fast_period\": 10}]'. "
        "The grid is capped in size (oversized requests are rejected, not "
        "silently truncated) -- keep it coarse, this is one round of a "
        "round-capped sweep-refine loop, not an unbounded search. The "
        "response's `completeness` field is the fraction of the REQUESTED "
        "grid that actually succeeded -- treat anything below your stated "
        "tolerance as a reason to distrust the ranked results, never as a "
        "clean pass on a smaller, silently-shrunk set."
    )
    parameters = {
        "type": "object",
        "properties": {
            "symbol": {"type": "string", "description": "Stock symbol"},
            "from_date": {"type": "string", "description": "Start date YYYY-MM-DD"},
            "to_date": {"type": "string", "description": "End date YYYY-MM-DD"},
            "recipe": {
                "type": "string",
                "description": "Recipe-mode: a built-in strategy template key (see list_sweep_recipes). Requires `param_grid` entries to carry the full parameter set.",
            },
            "base_code": {
                "type": "string",
                "description": "Base-code-mode: existing strategy source to vary one parameter of. Requires `param_name`.",
            },
            "param_name": {"type": "string", "description": "Base-code-mode: the parameter name each param_grid entry varies."},
            "param_grid": {
                "type": "string",
                "description": "JSON array of parameter dicts, one per grid point -- see mode descriptions above.",
            },
            "indicators": {
                "type": "string",
                "description": "Comma-separated indicator kinds to make available, e.g. 'sma_20,rsi_14' (optional)",
            },
            "initial_capital": {
                "type": "number",
                "description": "Starting capital for the backtest (optional, defaults to service config)",
            },
        },
        "required": ["symbol", "from_date", "to_date", "param_grid"],
    }
    is_readonly = False

    def __init__(self):
        self._services_config = {}

    def execute(self, **kwargs) -> str:
        param_grid = json.loads(kwargs["param_grid"])
        indicators = (
            [k.strip().lower() for k in kwargs["indicators"].split(",") if k.strip()]
            if kwargs.get("indicators") else None
        )

        try:
            result = asyncio.run(self._run_in_process(
                symbol=kwargs["symbol"], from_date=kwargs["from_date"], to_date=kwargs["to_date"],
                param_grid=param_grid, recipe=kwargs.get("recipe"), base_code=kwargs.get("base_code"),
                param_name=kwargs.get("param_name"), indicators=indicators,
                initial_capital=kwargs.get("initial_capital"),
            ))
            return json.dumps(_serialize_sweep_grid(result))
        except Exception as exc:
            LOG.debug("run_parameter_sweep: in-process run failed, falling back to HTTP: %s", exc)

        import httpx

        url = self._services_config.get("vinu_research", "http://localhost:8087")
        payload = {
            "symbol": kwargs["symbol"],
            "from_date": kwargs["from_date"],
            "to_date": kwargs["to_date"],
            "param_grid": param_grid,
        }
        if kwargs.get("recipe"):
            payload["recipe"] = kwargs["recipe"]
        if kwargs.get("base_code"):
            payload["base_code"] = kwargs["base_code"]
            if kwargs.get("param_name"):
                payload["param_name"] = kwargs["param_name"]
        if indicators:
            payload["indicators"] = indicators
        if kwargs.get("initial_capital") is not None:
            payload["initial_capital"] = kwargs["initial_capital"]

        resp = httpx.post(f"{url}/research/sweep/grid", json=payload, timeout=600)
        resp.raise_for_status()
        return resp.text

    async def _run_in_process(self, **kwargs):
        from vinu_research.sweep_grid import run_sweep_grid

        from ..broker.research_link import get_research_config, get_research_tools

        tools = get_research_tools(get_research_config())
        try:
            return await run_sweep_grid(tools=tools, **kwargs)
        finally:
            await tools.close()
