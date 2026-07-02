"""Feature computation engine: per-symbol load, compute, incremental parquet write."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from vinu_features.client.stock_price import CandleClient, StockPriceClient
from vinu_features.compute.registry import apply_indicators, expand_features, warmup_bars_for_features
from vinu_features.engine.manifest import write_manifest
from vinu_features.storage.models import FeatureRequest

_PARQUET_NAME = "features.parquet"
_OUTPUT_COLUMNS = ("ts", "symbol", "open", "high", "low", "close", "volume")


class FeatureEngine:
    def __init__(self, client: CandleClient | None = None) -> None:
        self.client = client or StockPriceClient()

    def run_dir_for(self, data_root: Path, request: FeatureRequest) -> Path:
        assert request.id is not None
        return data_root / "runs" / f"{request.id}_{request.slug}"

    def process(self, request: FeatureRequest, *, data_root: Path) -> tuple[Path, int]:
        assert request.id is not None
        run_dir = self.run_dir_for(data_root, request)
        run_dir.mkdir(parents=True, exist_ok=True)
        parquet_path = run_dir / _PARQUET_NAME

        if parquet_path.exists():
            parquet_path.unlink()

        feature_cols = expand_features(request.features)
        warmup = warmup_bars_for_features(feature_cols)
        interval_seconds = _interval_seconds(request.interval)
        warmup_from = request.from_ts - warmup * interval_seconds

        total_rows = 0
        writer: pq.ParquetWriter | None = None
        schema: pa.Schema | None = None

        try:
            for symbol in request.symbols:
                rows = self.client.fetch_candles(
                    symbol,
                    interval=request.interval,
                    from_ts=warmup_from,
                    to_ts=request.to_ts,
                )
                rows = _normalize_rows(rows, symbol)
                rows = [r for r in rows if request.from_ts <= int(r["ts"]) <= request.to_ts]
                if not rows:
                    continue
                enriched = apply_indicators(rows, feature_cols)
                table = _rows_to_table(enriched, feature_cols)
                if writer is None:
                    schema = table.schema
                    writer = pq.ParquetWriter(parquet_path, schema)
                writer.write_table(table)
                total_rows += table.num_rows

            if writer is None:
                empty = _empty_table(feature_cols)
                pq.write_table(empty, parquet_path)
                total_rows = 0
        finally:
            if writer is not None:
                writer.close()

        write_manifest(
            run_dir / "manifest.md",
            request,
            row_count=total_rows,
            parquet_name=_PARQUET_NAME,
        )
        return run_dir, total_rows


def _interval_seconds(interval: str) -> int:
    mapping = {
        "1m": 60,
        "5m": 300,
        "15m": 900,
        "1h": 3600,
        "1d": 86400,
    }
    if interval not in mapping:
        raise ValueError(f"Unsupported interval: {interval}")
    return mapping[interval]


def _normalize_rows(rows: list[dict[str, Any]], symbol: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        ts = row.get("ts") or row.get("timestamp") or row.get("sort_ts")
        if ts is None:
            continue
        out.append(
            {
                "ts": int(ts),
                "symbol": symbol.upper(),
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": float(row.get("volume") or 0),
            }
        )
    out.sort(key=lambda r: r["ts"])
    return out


def _rows_to_table(rows: list[dict[str, Any]], features: list[str]) -> pa.Table:
    columns: dict[str, list[Any]] = {c: [] for c in _OUTPUT_COLUMNS}
    for feat in features:
        columns[feat] = []
    for row in rows:
        for col in _OUTPUT_COLUMNS:
            columns[col].append(row[col])
        for feat in features:
            val = row.get(feat)
            columns[feat].append(float(val) if val is not None else None)
    return pa.table(columns)


def _empty_table(features: list[str]) -> pa.Table:
    columns: dict[str, list[Any]] = {c: [] for c in _OUTPUT_COLUMNS}
    for feat in features:
        columns[feat] = []
    return pa.table(columns)
