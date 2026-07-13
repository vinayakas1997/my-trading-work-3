"""Resolve Parquet paths under VINU_STOCK_DATA_ROOT."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path


def prices_root(data_root: Path) -> Path:
    return data_root / "prices" / "1m"


def symbol_dir(data_root: Path, symbol: str) -> Path:
    return prices_root(data_root) / symbol.strip().upper()


def archive_dir(data_root: Path, symbol: str) -> Path:
    return symbol_dir(data_root, symbol) / "archive"


def live_dir(data_root: Path, symbol: str) -> Path:
    return symbol_dir(data_root, symbol) / "live"


def archive_year_path(data_root: Path, symbol: str, year: int) -> Path:
    return archive_dir(data_root, symbol) / f"{year}.parquet"


def live_year_path(data_root: Path, symbol: str, year: int) -> Path:
    return live_dir(data_root, symbol) / f"{year}.parquet"


def parquet_globs(data_root: Path, symbol: str) -> list[str]:
    """Glob patterns for DuckDB read_parquet (archive + live)."""
    sym = symbol.strip().upper()
    base = prices_root(data_root) / sym
    patterns: list[str] = []
    archive = base / "archive"
    live = base / "live"
    if archive.is_dir():
        patterns.append(str(archive / "*.parquet"))
    if live.is_dir():
        patterns.append(str(live / "*.parquet"))
    return patterns


def parquet_globs_by_range(
    data_root: Path,
    symbol: str,
    *,
    from_ts: int | None = None,
    to_ts: int | None = None,
) -> list[str]:
    """Glob patterns filtered to year range for partition pruning."""
    if from_ts is None and to_ts is None:
        return parquet_globs(data_root, symbol)

    sym = symbol.strip().upper()
    base = prices_root(data_root) / sym
    now = datetime.now(timezone.utc)
    start_year = datetime.fromtimestamp(from_ts, tz=timezone.utc).year if from_ts else 1900
    end_year = datetime.fromtimestamp(to_ts, tz=timezone.utc).year if to_ts else now.year
    patterns: list[str] = []

    archive = base / "archive"
    if archive.is_dir():
        for year in range(start_year, end_year + 1):
            yf = archive / f"{year}.parquet"
            if yf.is_file():
                patterns.append(str(yf))

    live = base / "live"
    if live.is_dir():
        for year in range(start_year, end_year + 1):
            patterns.append(str(live / f"{year}*.parquet"))

    if not patterns:
        return parquet_globs(data_root, symbol)

    return patterns
