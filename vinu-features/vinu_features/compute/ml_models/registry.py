"""ML model dispatch registry."""

from __future__ import annotations

import importlib
from typing import Any

_MODEL_MODULES: list[Any] = []
for _mod_name in (
    "linear_regression",
    "ridge",
    "lasso",
    "elastic_net",
    "logistic_regression",
    "random_forest",
    "lightgbm",
    "xgboost",
    "catboost",
):
    _MODEL_MODULES.append(
        importlib.import_module(f"vinu_features.compute.ml_models.{_mod_name}.{_mod_name}")
    )

_MODELS: dict[str, Any] = {mod.NAME: mod for mod in _MODEL_MODULES}
_ALIASES: dict[str, str] = {}
for mod in _MODEL_MODULES:
    for alias in mod.ALIASES:
        _ALIASES[alias.strip().lower()] = mod.NAME


def list_models() -> list[str]:
    return sorted(_MODELS.keys())


def get_model(name: str) -> Any:
    key = name.strip().lower()
    canonical = _ALIASES.get(key, key)
    if canonical not in _MODELS:
        raise ValueError(f"Unknown ml_model: {name}")
    return _MODELS[canonical]


def score(model_name: str, X: list[list[float]], y: list[float]) -> list[float]:
    return get_model(model_name).score(X, y)
