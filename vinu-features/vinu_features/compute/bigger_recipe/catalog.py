"""Recipe catalog: thin dispatch over recipe modules."""

from __future__ import annotations

import importlib
from typing import Any

_RECIPE_MODULES: list[Any] = []
for _mod_name in (
    "basic_ta",
    "swing_basic",
    "momentum",
    "trend_pack",
    "volatility_pack",
    "volume_pack",
    "mean_reversion_pack",
    "full_ta",
    "alpha101",
    "alpha158",
    "alpha360",
):
    _RECIPE_MODULES.append(
        importlib.import_module(f"vinu_features.compute.bigger_recipe.{_mod_name}.{_mod_name}")
    )

_RECIPES: dict[str, Any] = {mod.NAME: mod for mod in _RECIPE_MODULES}


def is_recipe(name: str) -> bool:
    return name.strip().lower() in _RECIPES


def list_recipe_names() -> list[str]:
    return sorted(_RECIPES.keys())


def resolve(name: str) -> tuple[str, ...]:
    key = name.strip().lower()
    if key not in _RECIPES:
        raise ValueError(f"Unknown recipe: {name}")
    return _RECIPES[key].resolve()


def warmup_for(name: str) -> int:
    key = name.strip().lower()
    return int(_RECIPES[key].WARMUP_BARS)


def get_recipe_meta(name: str) -> dict:
    key = name.strip().lower()
    mod = _RECIPES[key]
    meta: dict = {
        "description": mod.DESCRIPTION,
        "warmup": mod.WARMUP_BARS,
    }
    if hasattr(mod, "FEATURE_NAMES"):
        meta["features"] = mod.FEATURE_NAMES
    else:
        meta["alpha"] = key
    return meta


def list_all_presets() -> list[dict]:
    out = []
    for name in sorted(_RECIPES.keys()):
        mod = _RECIPES[name]
        feats = mod.resolve()
        out.append({
            "name": name,
            "description": mod.DESCRIPTION,
            "features": list(feats),
            "feature_count": len(feats),
        })
    return out


def compute_recipe(rows: list[dict], name: str) -> dict[str, list[float | None]]:
    key = name.strip().lower()
    if key not in _RECIPES:
        raise ValueError(f"Unknown recipe: {name}")
    return _RECIPES[key].compute(rows)
