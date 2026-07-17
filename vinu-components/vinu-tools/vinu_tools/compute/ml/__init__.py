"""Machine learning models for factor-based prediction.

Entry points:
    train(model, X, y)              → fitted model + in-sample predictions
    train_predict(model, X_train, y_train, X_test) → train + test predictions
    predict(model, X)               → predictions from fitted model
    evaluate(y_true, y_pred)        → Spearman IC + metrics
    select_best(X_train, y_train, X_test, y_test) → auto-select best model
    list_models()                   → available model names
    create_label(rows, label_type)  → build forward return labels
    normalize(values)               → z-score normalization
"""

from vinu_tools.compute.ml.train import train, train_predict, predict
from vinu_tools.compute.ml.evaluate import evaluate
from vinu_tools.compute.ml.select import list_models, select_best, get_model
from vinu_tools.compute.ml.labels import create_label
from vinu_tools.compute.ml.preprocess import normalize

__all__ = [
    "train", "train_predict", "predict",
    "evaluate",
    "list_models", "select_best", "get_model",
    "create_label",
    "normalize",
]
