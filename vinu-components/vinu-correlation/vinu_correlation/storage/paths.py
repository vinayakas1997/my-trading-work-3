from __future__ import annotations

from pathlib import Path


def impact_path(data_root: Path, symbol: str, year: int) -> Path:
    return data_root / "correlation" / symbol.upper() / f"{year}.parquet"


def baseline_path(data_root: Path, symbol: str, year: int) -> Path:
    return data_root / "correlation" / symbol.upper() / f"{year}_baseline.parquet"


def correlation_path(data_root: Path, symbol: str, year: int) -> Path:
    return data_root / "correlation" / symbol.upper() / f"{year}_correlation.parquet"


def symbol_dir(data_root: Path, symbol: str) -> Path:
    return data_root / "correlation" / symbol.upper()
