import json
from typing import Any

from ..agent.angle_consensus import compare_categorical, compare_directional, compare_magnitude
from ..agent.tools import BaseTool


class CompareAnglesTool(BaseTool):
    name = "compare_angles"
    description = (
        "Cross-check whether two angles agree or diverge for the same ticker (Phase 8) -- pass "
        "the real values you already got from get_all_angles, this tool does the deterministic "
        "comparison (never an LLM guess, so the same two angles always get the same verdict). "
        "Three comparison_type values: 'directional' (compares sign, e.g. a forecast's up/down "
        "direction), 'magnitude' (compares relative distance against a tolerance, e.g. two "
        "numeric forecast values), 'categorical' (exact-match or a configured adjacency rule, "
        "e.g. a regime label vs. a lifecycle stage). If either angle's row_count is 0, this "
        "reports 'insufficient_data' -- never forces an agree/diverge verdict out of missing data."
    )
    parameters = {
        "type": "object",
        "properties": {
            "comparison_type": {"type": "string", "enum": ["directional", "magnitude", "categorical"]},
            "angle_a_name": {"type": "string"},
            "angle_a_row_count": {"type": "integer"},
            "angle_a_value": {"description": "The real value from get_all_angles's output -- a number for directional/magnitude, a string label for categorical."},
            "angle_b_name": {"type": "string"},
            "angle_b_row_count": {"type": "integer"},
            "angle_b_value": {"description": "Same shape as angle_a_value."},
            "tolerance": {"type": "number", "description": "magnitude mode only -- relative-distance tolerance (default 0.15)"},
        },
        "required": ["comparison_type", "angle_a_name", "angle_a_row_count", "angle_a_value", "angle_b_name", "angle_b_row_count", "angle_b_value"],
    }
    is_readonly = True

    def execute(self, **kwargs: Any) -> str:
        comparison_type = kwargs["comparison_type"]
        common = (
            kwargs["angle_a_name"], kwargs["angle_a_row_count"], kwargs["angle_a_value"],
            kwargs["angle_b_name"], kwargs["angle_b_row_count"], kwargs["angle_b_value"],
        )
        if comparison_type == "directional":
            result = compare_directional(*common)
        elif comparison_type == "magnitude":
            extra = {"tolerance": kwargs["tolerance"]} if "tolerance" in kwargs else {}
            result = compare_magnitude(*common, **extra)
        elif comparison_type == "categorical":
            result = compare_categorical(*common)
        else:
            return json.dumps({"status": "error", "error": f"unknown comparison_type {comparison_type!r}"})

        return json.dumps({
            "status": "ok",
            "outcome": result.outcome,
            "reasoning": result.reasoning,
            "angle_a_name": result.angle_a_name,
            "angle_b_name": result.angle_b_name,
        })
