"""Parse and resolve user feature specs to column names."""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass
from typing import Any

from vinu_features.compute.bigger_recipe import catalog as recipe_catalog
from vinu_features.compute.feature_catalog import get_indicator, get_indicator_module, list_indicator_kinds
from vinu_features.compute.indicators._shared.spec import (
    column_matches_meta,
    default_params,
    format_columns,
    meta_from_module,
    params_from_column_name,
    validate_params,
)


@dataclass(frozen=True)
class FeatureSpec:
    kind: str
    params: dict[str, int | float]


def _parse_spec_string(raw: str) -> FeatureSpec | str:
    text = raw.strip()
    if not text:
        raise ValueError("Empty feature spec")
    if ":" not in text:
        kind = text.lower()
        if kind in list_indicator_kinds():
            return FeatureSpec(kind=kind, params={})
        return text
    kind, _, rest = text.partition(":")
    kind = kind.strip().lower()
    if not rest:
        return FeatureSpec(kind=kind, params={})
    params: dict[str, int | float] = {}
    for part in rest.split(","):
        part = part.strip()
        if not part:
            continue
        if "=" not in part:
            raise ValueError(f"Invalid param segment {part!r} in {raw!r}. Use key=value")
        key, val = part.split("=", 1)
        key = key.strip()
        val = val.strip()
        params[key] = int(val) if re.fullmatch(r"-?\d+", val) else float(val)
    return FeatureSpec(kind=kind, params=params)


def parse_feature_input(raw: str | dict[str, Any]) -> FeatureSpec | str:
    if isinstance(raw, dict):
        kind = str(raw.get("kind", "")).strip().lower()
        if not kind:
            raise ValueError("Feature spec object requires 'kind'")
        params = raw.get("params") or {}
        if not isinstance(params, dict):
            raise ValueError("Feature spec 'params' must be an object")
        return FeatureSpec(kind=kind, params=dict(params))
    if isinstance(raw, str):
        if recipe_catalog.is_recipe(raw.strip().lower()):
            return raw.strip().lower()
        return _parse_spec_string(raw)
    raise ValueError(f"Invalid feature input type: {type(raw).__name__}")


def _resolve_spec(spec: FeatureSpec) -> list[str]:
    kind = spec.kind
    try:
        meta = get_indicator(kind)
        mod = get_indicator_module(kind)
    except ValueError as exc:
        kinds = list_indicator_kinds()
        close = difflib.get_close_matches(kind, kinds, n=1)
        hint = f" Did you mean '{close[0]}'?" if close else ""
        raise ValueError(
            f"Unknown indicator {kind!r}.{hint} Run: vinu-features features help"
        ) from exc
    merged = {**default_params(meta), **validate_params(meta, spec.params)}
    if hasattr(mod, "resolve_spec_columns"):
        return list(mod.resolve_spec_columns(merged))
    return list(format_columns(meta, merged))


def _resolve_legacy_string(name: str) -> str:
    key = name.strip().lower()
    if recipe_catalog.is_recipe(key):
        return key

    from vinu_features.compute.registry import _find_indicator_module, validate_feature_name  # noqa: PLC0415

    for mod in _indicator_meta_modules():
        meta = meta_from_module(mod)
        if column_matches_meta(meta, key):
            return key

    if _find_indicator_module(key) is not None:
        return key

    try:
        validate_feature_name(key)
    except ValueError as exc:
        m = re.match(r"^([a-z_]+)_(\d+)$", key)
        if m:
            base, period = m.group(1), m.group(2)
            if base in list_indicator_kinds():
                raise ValueError(
                    f"Unknown feature {name!r}. Try: --feature {base}:period={period}"
                ) from exc
        raise
    return key


def _indicator_meta_modules() -> list[Any]:
    from vinu_features.compute.feature_catalog import _load_modules  # noqa: PLC0415

    return _load_modules()


def resolve_one(raw: str | dict[str, Any]) -> list[str]:
    parsed = parse_feature_input(raw)
    if isinstance(parsed, str):
        if recipe_catalog.is_recipe(parsed):
            return list(recipe_catalog.resolve(parsed))
        return [_resolve_legacy_string(parsed)]
    return _resolve_spec(parsed)


def validate_and_resolve(inputs: list[str | dict[str, Any]]) -> list[str]:
    if not inputs:
        raise ValueError("At least one feature is required")
    out: list[str] = []
    seen: set[str] = set()
    for raw in inputs:
        for col in resolve_one(raw):
            if col not in seen:
                seen.add(col)
                out.append(col)
    if not out:
        raise ValueError("At least one feature is required")

    from vinu_features.compute.registry import expand_features, validate_feature_name  # noqa: PLC0415

    expanded = expand_features(out)
    for n in expanded:
        validate_feature_name(n)
    return expanded
