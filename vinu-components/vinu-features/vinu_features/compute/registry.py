"""Central dispatch for indicators, recipes, and alpha columns."""

from __future__ import annotations

import importlib
from typing import Any, Sequence

from vinu_features.compute.bigger_recipe import catalog as recipe_catalog
from vinu_features.compute.indicators._module_names import INDICATOR_MODULE_NAMES

_INDICATOR_MODULES: list[Any] | None = None
_ALPHA158_NAMES: set[str] | None = None
_ALPHA360_NAMES: set[str] | None = None
_ALPHA101_NAMES: set[str] | None = None


def _get_indicator_modules() -> list[Any]:
    global _INDICATOR_MODULES
    if _INDICATOR_MODULES is None:
        _INDICATOR_MODULES = [
            importlib.import_module(f"vinu_features.compute.indicators.{name}.{name}")
            for name in INDICATOR_MODULE_NAMES
        ]
    return _INDICATOR_MODULES


def _alpha_name_sets() -> tuple[set[str], set[str], set[str]]:
    global _ALPHA158_NAMES, _ALPHA360_NAMES, _ALPHA101_NAMES
    if _ALPHA158_NAMES is None:
        _ALPHA158_NAMES = set(recipe_catalog.resolve("alpha158"))
        _ALPHA360_NAMES = set(recipe_catalog.resolve("alpha360"))
        _ALPHA101_NAMES = set(recipe_catalog.resolve("alpha101"))
    return _ALPHA158_NAMES, _ALPHA360_NAMES, _ALPHA101_NAMES


def expand_recipe(name: str) -> list[str]:
    return list(recipe_catalog.resolve(name))


def expand_features(names: Sequence[str]) -> list[str]:
    out: list[str] = []
    for raw in names:
        name = raw.strip().lower()
        if not name:
            continue
        if recipe_catalog.is_recipe(name):
            out.extend(recipe_catalog.resolve(name))
        else:
            out.append(name)
    seen: set[str] = set()
    deduped: list[str] = []
    for n in out:
        if n not in seen:
            seen.add(n)
            deduped.append(n)
    return deduped


def parse_feature_names(names: Sequence[str]) -> list[str]:
    from vinu_features.compute.feature_spec import validate_and_resolve  # noqa: PLC0415

    return validate_and_resolve(list(names))


def validate_feature_name(name: str) -> None:
    if recipe_catalog.is_recipe(name):
        return
    a158, a360, a101 = _alpha_name_sets()
    if name in a158 or name in a360 or name in a101:
        return
    if _find_indicator_module(name) is not None:
        return
    raise ValueError(f"Unknown feature: {name}")


def list_known_features() -> list[str]:
    from vinu_features.compute.feature_catalog import list_indicators

    base: list[str] = []
    for meta in list_indicators():
        params = {k: v.default for k, v in meta.params.items()}
        for col in meta.output_columns:
            base.append(col.format(**params))
    for p in (5, 10, 20, 50, 100):
        base.append(f"sma_{p}")
    for p in (12, 26, 50):
        base.append(f"ema_{p}")
    return base + recipe_catalog.list_recipe_names()


def warmup_bars_for_features(features: Sequence[str]) -> int:
    expanded = expand_features(features)
    need = 1
    a158, a360, a101 = _alpha_name_sets()
    for name in expanded:
        if recipe_catalog.is_recipe(name):
            need = max(need, recipe_catalog.warmup_for(name))
        elif name in a158 or name in a360 or name in a101:
            need = max(need, 60)
        else:
            mod = _find_indicator_module(name)
            if mod is not None:
                need = max(need, mod.warmup_for(name))
    return need


def apply_indicators(rows: list[dict], names: Sequence[str]) -> list[dict]:
    if not rows or not names:
        return rows
    expanded = expand_features(names)
    out = [dict(r) for r in rows]
    a158, a360, a101 = _alpha_name_sets()

    if any(n in a101 for n in expanded):
        cols = recipe_catalog.compute_recipe(rows, "alpha101")
        for i, row in enumerate(out):
            for n in expanded:
                if n in cols:
                    row[n] = cols[n][i]
    if any(n in a158 for n in expanded):
        cols = recipe_catalog.compute_recipe(rows, "alpha158")
        for i, row in enumerate(out):
            for n in expanded:
                if n in cols:
                    row[n] = cols[n][i]
    if any(n in a360 for n in expanded):
        cols = recipe_catalog.compute_recipe(rows, "alpha360")
        for i, row in enumerate(out):
            for n in expanded:
                if n in cols:
                    row[n] = cols[n][i]

    for name in expanded:
        if name in a158 or name in a360 or name in a101:
            continue
        mod = _find_indicator_module(name)
        if mod is None:
            continue
        cols = mod.compute(rows, name=name)
        for i, row in enumerate(out):
            for col, vals in cols.items():
                if col == name:
                    row[col] = vals[i]
                elif col in expanded and col not in row:
                    row[col] = vals[i]
    return out


def _find_indicator_module(name: str) -> Any | None:
    for mod in _get_indicator_modules():
        if mod.matches(name):
            return mod
    return None
