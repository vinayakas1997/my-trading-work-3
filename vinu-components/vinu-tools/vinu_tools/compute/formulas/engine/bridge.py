"""Bridge function: single entry point for computing any factor with param overrides.

Usage:
    from vinu_tools.compute.formulas.engine import compute_factor

    result = compute_factor("gtja191_001", panel)
    result = compute_factor("gtja191_001", panel, params={"window": 10})
    result = compute_factor("alpha101_001", panel)
"""

from __future__ import annotations

import importlib
import logging
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

LOG = logging.getLogger(__name__)

_CATALOG_DIR = Path(__file__).resolve().parent.parent / "catalog"
_FACTOR_ROOT = Path(__file__).resolve().parent.parent.parent / "factors" / "singles"
_CATALOG_CACHE: dict[str, dict[str, Any]] = {}
_IMPORT_CACHE: dict[str, Any] = {}


def _load_catalog(group: str) -> dict[str, Any]:
    """Load one YAML catalog file and cache it."""
    if group not in _CATALOG_CACHE:
        path = _CATALOG_DIR / f"{group}.yaml"
        if not path.exists():
            raise FileNotFoundError(f"Catalog not found: {path}")
        with open(path, encoding="utf-8") as f:
            _CATALOG_CACHE[group] = yaml.safe_load(f) or {}
    return _CATALOG_CACHE[group]


def resolve_factor_spec(factor_id: str) -> dict[str, Any] | None:
    """Look up a factor spec by ID across all catalog groups."""
    for yaml_path in sorted(_CATALOG_DIR.glob("*.yaml")):
        group = yaml_path.stem
        catalog = _load_catalog(group)
        if factor_id in catalog:
            spec = dict(catalog[factor_id])
            spec["_group"] = group
            return spec
    return None


def _import_factor_module(source_path: str) -> Any:
    """Import a factor's compute module from its source path."""
    if source_path in _IMPORT_CACHE:
        return _IMPORT_CACHE[source_path]

    if source_path.startswith("factors/singles/"):
        rel_path = source_path.replace("factors/singles/", "").replace(".py", "")
        module_path = f"vinu_tools.compute.factors.singles.{rel_path.replace('/', '.')}"
    else:
        raise ValueError(f"Cannot resolve source path: {source_path}")

    mod = importlib.import_module(module_path)
    _IMPORT_CACHE[source_path] = mod
    return mod


def _validate_params(spec: dict[str, Any], params: dict[str, Any] | None) -> dict[str, Any]:
    """Merge user params with defaults and validate against ranges."""
    merged: dict[str, Any] = {}

    param_defs = spec.get("params", {})
    if not param_defs:
        return merged

    for param_name, pdef in param_defs.items():
        default = pdef.get("default")
        value = (params or {}).get(param_name, default)

        param_range = pdef.get("range")
        if param_range:
            lo, hi = param_range
            if lo is not None and value < lo:
                raise ValueError(f"{spec['id']}.{param_name}: {value} < min {lo}")
            if hi is not None and value > hi:
                raise ValueError(f"{spec['id']}.{param_name}: {value} > max {hi}")

        merged[param_name] = value

    return merged


def compute_factor(
    factor_id: str,
    panel: dict[str, pd.DataFrame],
    params: dict[str, Any] | None = None,
) -> pd.DataFrame:
    """Compute a factor by its ID with optional param overrides.

    Args:
        factor_id: e.g. "gtja191_001", "alpha101_005", "fund_roe"
        panel: dict of {column_name: pd.DataFrame(T x N)}
        params: optional dict overriding default params from YAML catalog.
                Values are validated against ranges defined in the catalog.

    Returns:
        pd.DataFrame(T x N) of factor values
    """
    spec = resolve_factor_spec(factor_id)
    if spec is None:
        raise ValueError(f"Unknown factor: {factor_id}")

    source = spec.get("source", "")
    if not source:
        raise ValueError(f"No source path for {factor_id}")

    merged = _validate_params(spec, params)

    mod = _import_factor_module(source)
    if not hasattr(mod, "compute"):
        raise ValueError(f"Module {source} has no compute() function")

    result = mod.compute(panel, **merged)
    if result is None:
        raise RuntimeError(f"{factor_id}.compute() returned None")
    return result
