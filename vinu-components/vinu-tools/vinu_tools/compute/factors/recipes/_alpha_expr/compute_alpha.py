"""Shared alpha column computation."""

from __future__ import annotations

from typing import Callable

from vinu_tools.compute.factors.recipes._alpha_expr.evaluator import evaluate, rows_to_arrays

GetFeatureConfig = Callable[[], tuple[list[str], list[str]]]

_CACHE: dict[str, tuple[list[str], list[str]]] = {}


def get_fields_and_names(kind: str, getter: GetFeatureConfig) -> tuple[list[str], list[str]]:
    if kind not in _CACHE:
        _CACHE[kind] = getter()
    return _CACHE[kind]


def compute_alpha(rows: list[dict], getter: GetFeatureConfig, subset: set[str] | None = None) -> dict[str, list[float | None]]:
    fields, names = getter()
    if subset:
        pairs = [(f, n) for f, n in zip(fields, names) if n in subset]
        if not pairs:
            return {}
        fields, names = zip(*pairs)
    arrays = rows_to_arrays(rows)
    out: dict[str, list[float | None]] = {}
    for expr, col in zip(fields, names):
        out[col] = evaluate(expr, arrays)
    return out
