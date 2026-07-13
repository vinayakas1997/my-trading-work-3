"""ML model dispatch — train and score on feature parquet."""

from __future__ import annotations

from pathlib import Path

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

    scores = registry.score(ml_model, X, y_clean)
    out_rows = []
    for i, idx in enumerate(valid_idx):
        rec = dict(rows[idx])
        rec["ml_score"] = scores[i]
        out_rows.append(rec)

    out_path = run_dir / "scores.parquet"
    pq.write_table(pa.Table.from_pylist(out_rows), out_path)
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
