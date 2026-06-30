"""Resolve Parquet paths under VINU_STOCK_DATA_ROOT."""

from __future__ import annotations

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
