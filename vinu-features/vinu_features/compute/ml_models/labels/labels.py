"""Label generation for ML models."""

from __future__ import annotations

from typing import Any

import pyarrow.parquet as pq


def forward_return(rows: list[dict], *, periods: int = 1) -> list[float | None]:
    closes = [float(r["close"]) for r in rows]
    out: list[float | None] = [None] * len(closes)
    for i in range(len(closes) - periods):
        prev = closes[i]
        out[i] = (closes[i + periods] - prev) / prev if prev else None
    return out


def build_label_column(rows: list[dict], label: str) -> list[float | None]:
    if label in ("forward_return_1", "fwd_ret_1", "label"):
        return forward_return(rows, periods=1)
    if label == "forward_return_5":
        return forward_return(rows, periods=5)
    raise ValueError(f"Unknown label: {label}")
