"""ML model dispatch registry."""

from __future__ import annotations

import importlib
import logging
from typing import Any

import numpy as np

LOG = logging.getLogger(__name__)

_MODEL_MODULES: list[Any] | None = None
_MODELS: dict[str, Any] | None = None
_ALIASES: dict[str, str] | None = None


def _ensure_loaded() -> None:
    global _MODEL_MODULES, _MODELS, _ALIASES
    if _MODELS is not None:
        return
    _MODEL_MODULES = [
        importlib.import_module(f"vinu_tools.compute.ml.models.{n}.{n}")
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


def train_and_predict(
    model_name: str,
    X_train: list[list[float]],
    y_train: list[float],
    X_test: list[list[float]],
) -> tuple[list[float], list[float]]:
    """Fit on train, predict on both train and test. Returns (train_preds, test_preds)."""
    mod = get_model(model_name)
    model = mod.create()
    arr_train = np.array(X_train)
    arr_test = np.array(X_test)
    model.fit(arr_train, y_train)
    train_preds = model.predict(arr_train).tolist()
    test_preds = model.predict(arr_test).tolist() if len(X_test) > 0 else []
    return train_preds, test_preds


def oos_ic(y_true: list[float], y_pred: list[float]) -> float:
    """Out-of-sample Information Coefficient (Spearman rank correlation)."""
    if len(y_true) < 5 or len(y_pred) < 5:
        return 0.0
    from scipy.stats import spearmanr
    corr, _ = spearmanr(y_true, y_pred)
    return float(corr) if not np.isnan(corr) else 0.0


def select_best(
    X_train: list[list[float]],
    y_train: list[float],
    X_test: list[list[float]],
    y_test: list[float],
    candidates: list[str] | None = None,
) -> tuple[str, float]:
    """
    Run multiple models and return (best_model_name, oos_ic) ranked by
    out-of-sample Information Coefficient. Skips models that fail to train.
    """
    _ensure_loaded()
    if candidates is None:
        candidates = sorted(_MODELS.keys())

    best_name: str = candidates[0]
    best_ic: float = -999.0

    for name in candidates:
        try:
            _, test_preds = train_and_predict(name, X_train, y_train, X_test)
            ic = oos_ic(y_test, test_preds)
            LOG.info("select_best: %s OOS IC = %.4f", name, ic)
            if ic > best_ic:
                best_ic = ic
                best_name = name
        except Exception as exc:
            LOG.warning("select_best: %s failed — %s", name, exc)
            continue

    return best_name, best_ic
