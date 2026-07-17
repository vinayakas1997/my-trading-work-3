"""Training interface — wraps ml_models registry."""

from typing import Any
import numpy as np
from vinu_tools.compute.ml.models.registry import train_and_predict as _train_and_predict
from vinu_tools.compute.ml.models.registry import score as _score


def train(
    model_name: str, X, y,
) -> tuple[Any, list[float]]:
    """Fit model on (X, y) and return (fitted_estimator, in_sample_predictions)."""
    from vinu_tools.compute.ml.models.registry import get_model
    mod = get_model(model_name)
    import numpy as np
    X_arr = np.array(X) if not isinstance(X, np.ndarray) else X
    y_arr = np.array(y) if not isinstance(y, np.ndarray) else y
    estimator = mod.create()
    estimator.fit(X_arr, y_arr)
    preds = estimator.predict(X_arr).tolist()
    return estimator, preds


def train_predict(
    model_name: str, X_train, y_train, X_test,
) -> tuple[list[float], list[float]]:
    """Fit on train, return (train_preds, test_preds)."""
    return _train_and_predict(model_name, X_train, y_train, X_test)


def predict(model, X) -> list[float]:
    """Predict from a fitted estimator."""
    import numpy as np
    X_arr = np.array(X) if not isinstance(X, np.ndarray) else X
    return model.predict(X_arr).tolist()
