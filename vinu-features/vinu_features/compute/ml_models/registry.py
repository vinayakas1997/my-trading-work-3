"""ML model dispatch registry."""

from __future__ import annotations

import importlib
from typing import Any

_MODEL_MODULES: list[Any] | None = None
_MODELS: dict[str, Any] | None = None
_ALIASES: dict[str, str] | None = None


def _ensure_loaded() -> None:
    global _MODEL_MODULES, _MODELS, _ALIASES
    if _MODELS is not None:
        return
    _MODEL_MODULES = [
        importlib.import_module(f"vinu_features.compute.ml_models.{n}.{n}")
        for n in (
            "linear_regression", "ridge", "lasso", "elastic_net",
            "logistic_regression", "random_forest", "lightgbm",
            "xgboost", "catboost",
        )
    ]
    _MODELS = {mod.NAME: mod for mod in _MODEL_MODULES}
    _ALIASES = {}
    for mod in _MODEL_MODULES:
        for alias in mod.ALIASES:
            _ALIASES[alias.strip().lower()] = mod.NAME


def list_models() -> list[str]:
    _ensure_loaded()
    return sorted(_MODELS.keys())


def get_model(name: str) -> Any:
    _ensure_loaded()
    key = name.strip().lower()
    canonical = _ALIASES.get(key, key)
    if canonical not in _MODELS:
        raise ValueError(f"Unknown ml_model: {name}")
    return _MODELS[canonical]


def score(model_name: str, X: list[list[float]], y: list[float]) -> list[float]:
    return get_model(model_name).score(X, y)
