import json
from ..agent.tools import BaseTool


class FactorAnalysisTool(BaseTool):
    name = "factor_analysis"
    description = """Analyze and select alpha factors from the factor zoo (461 factors across 5 families).
Supports listing themes, filtering factors by attributes, and getting detailed info about a specific factor.
Use this to find the right factors for a given trading strategy or market regime."""

    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "Action to perform",
                "enum": [
                    "list_themes",
                    "filter",
                    "describe",
                    "list_zoos",
                    "count",
                ],
            },
            "theme": {
                "type": "string",
                "description": "Factor theme to filter by (e.g. momentum, reversal, volatility, volume, microstructure)",
            },
            "zoo": {
                "type": "string",
                "description": "Factor family to filter by (alpha101, gtja191, qlib158, academic, fundamental)",
            },
            "universe": {
                "type": "string",
                "description": "Target universe (equity_us, equity_cn, equity_hk, equity_in)",
            },
            "alpha_id": {
                "type": "string",
                "description": "Specific factor ID to describe (e.g. alpha101_001, gtja191_005)",
            },
            "limit": {
                "type": "integer",
                "description": "Max results to return (default 20, max 100)",
            },
        },
        "required": ["action"],
    }
    is_readonly = True

    def __init__(self) -> None:
        self._registry = None

    def _get_registry(self):
        if self._registry is None:
            from vinu_tools.compute.registry import get_alpha_registry
            self._registry = get_alpha_registry()
        return self._registry

    def execute(self, **kwargs) -> str:
        action = kwargs["action"]
        r = self._get_registry()

        if action == "count":
            return json.dumps({"status": "ok", "count": r.count()})

        if action == "list_themes":
            from vinu_tools.compute.alpha_meta import ALPHA_THEMES
            return json.dumps({
                "status": "ok",
                "themes": sorted(ALPHA_THEMES),
            })

        if action == "list_zoos":
            modules = r.list_alphas()
            by_zoo: dict[str, int] = {}
            for m in modules:
                zoo = m.meta.id.split("_")[0]
                by_zoo[zoo] = by_zoo.get(zoo, 0) + 1
            return json.dumps({
                "status": "ok",
                "zoos": [{"name": k, "count": v} for k, v in sorted(by_zoo.items())],
            })

        if action == "describe":
            alpha_id = kwargs.get("alpha_id", "")
            mod = r.get(alpha_id)
            if mod is None:
                return json.dumps({"status": "error", "error": f"Factor '{alpha_id}' not found"})
            meta = mod.meta
            return json.dumps({
                "status": "ok",
                "id": meta.id,
                "theme": meta.theme,
                "formula_latex": meta.formula_latex,
                "columns_required": meta.columns_required,
                "universe": meta.universe,
                "frequency": meta.frequency,
                "decay_horizon": meta.decay_horizon,
                "min_warmup_bars": meta.min_warmup_bars,
            })

        if action == "filter":
            modules = r.list_alphas()
            theme = kwargs.get("theme")
            zoo = kwargs.get("zoo")
            universe = kwargs.get("universe")
            limit = min(kwargs.get("limit", 20), 100)

            results = []
            for m in modules:
                meta = m.meta
                if theme and meta.theme != theme:
                    continue
                if zoo and not meta.id.startswith(zoo):
                    continue
                if universe and meta.universe != universe:
                    continue
                results.append({
                    "id": meta.id,
                    "theme": meta.theme,
                    "universe": meta.universe,
                    "frequency": meta.frequency,
                    "columns_required": meta.columns_required,
                    "decay_horizon": meta.decay_horizon,
                    "min_warmup_bars": meta.min_warmup_bars,
                })

            total = len(results)
            results = results[:limit]

            return json.dumps({
                "status": "ok",
                "count": len(results),
                "total_matching": total,
                "results": results,
            })

        return json.dumps({"status": "error", "error": f"Unknown action: {action}"})
