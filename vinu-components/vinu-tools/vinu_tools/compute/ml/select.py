"""Model selection interface — wraps ml_models registry."""

from vinu_tools.compute.ml.models.registry import (
    list_models,
    get_model as _get_model,
    train_and_predict,
    oos_ic,
)
from vinu_tools.compute.ml.models.registry import _ensure_loaded, _MODELS


def get_model(name: str):
    """Resolve model name/alias to module."""
    return _get_model(name)


def select_best(X_train, y_train, X_test, y_test, candidates=None):
    """Run multiple models, return (best_name, best_ic, results).

    candidates: list of model names, or None for all.
    results: list of dicts with name, ic, train_preds, test_preds.
    """
    _ensure_loaded()
    if candidates is None:
        candidates = sorted(_MODELS.keys())

    best_name: str = candidates[0]
    best_ic: float = -999.0
    results = []

    for name in candidates:
        try:
            tr_preds, te_preds = train_and_predict(name, X_train, y_train, X_test)
            ic = oos_ic(y_test, te_preds)
            results.append({"name": name, "ic": ic, "train_preds": tr_preds, "test_preds": te_preds})
            if ic > best_ic:
                best_ic = ic
                best_name = name
        except Exception:
            continue

    return best_name, best_ic, results
