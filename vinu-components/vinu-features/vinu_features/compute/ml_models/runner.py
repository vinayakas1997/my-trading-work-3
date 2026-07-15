"""ML model dispatch — train and score on feature parquet.

Uses time-ordered holdout split (first 80% train / last 20% test, no shuffle)
to produce honest out-of-sample scores. OOS IC is written alongside predictions.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

LOG = logging.getLogger(__name__)

import pyarrow as pa
import pyarrow.parquet as pq

from vinu_features.compute.ml_models.labels.labels import build_label_column
from vinu_features.compute.ml_models import registry


def run_ml_step(
    *,
    run_dir: Path,
    ml_model: str,
    ml_label: str,
    feature_columns: list[str],
) -> Path | None:
    parquet_path = run_dir / "features.parquet"
    if not parquet_path.exists():
        return None
    table = pq.read_table(parquet_path)
    rows = table.to_pylist()
    if len(rows) < 10:
        return None

    y = build_label_column(rows, ml_label)
    X, y_clean, valid_idx = _build_xy(rows, feature_columns, y)
    if len(X) < 10:
        return None

    # Time-ordered holdout split: first 80% train, last 20% test
    split = max(int(len(X) * 0.8), 1)
    X_train, y_train = X[:split], y_clean[:split]
    X_test, y_test = X[split:], y_clean[split:]

    train_preds, test_preds = registry.train_and_predict(
        ml_model, X_train, y_train, X_test
    )

    # OOS IC on test set
    oos = registry.oos_ic(y_test, test_preds)
    LOG.info("run_ml_step: %s OOS IC = %.4f (train=%d, test=%d)",
             ml_model, oos, len(X_train), len(X_test))

    # Write predictions for ALL rows (train preds for in-sample, test preds for OOS)
    out_rows = []
    train_end = len(train_preds)
    all_preds = train_preds + test_preds
    for i, idx in enumerate(valid_idx):
        rec = dict(rows[idx])
        rec["ml_score"] = all_preds[i]
        rec["ml_oos"] = i >= train_end  # mark which rows are out-of-sample
        out_rows.append(rec)

    out_path = run_dir / "scores.parquet"
    pq.write_table(pa.Table.from_pylist(out_rows), out_path)

    # Write OOS metrics alongside
    oos_metrics = {
        "ml_model": ml_model,
        "ml_label": ml_label,
        "oos_ic": oos,
        "train_count": len(X_train),
        "test_count": len(X_test),
    }
    oos_path = run_dir / "oos_metrics.json"
    oos_path.write_text(json.dumps(oos_metrics, indent=2))
    return out_path


def _build_xy(
    rows: list[dict], feature_columns: list[str], y: list[float | None]
) -> tuple[list[list[float]], list[float], list[int]]:
    X: list[list[float]] = []
    y_out: list[float] = []
    idx_out: list[int] = []
    for i, row in enumerate(rows):
        if y[i] is None:
            continue
        feats = []
        ok = True
        for col in feature_columns:
            v = row.get(col)
            if v is None:
                ok = False
                break
            feats.append(float(v))
        if ok:
            X.append(feats)
            y_out.append(float(y[i]))
            idx_out.append(i)
    return X, y_out, idx_out
