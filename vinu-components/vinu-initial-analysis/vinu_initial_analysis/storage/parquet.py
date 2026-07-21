from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq


FIXED_COLUMNS = ["symbol", "angle_name", "time_format", "run_id", "started_at", "analysis_from", "analysis_until", "stored_at"]


class AngleStorage:
    """Schema-agnostic parquet storage.

    Each write is partitioned by symbol/angle_name/.
    Fixed metadata columns are auto-stamped — the angle only provides its data columns.
    """

    def __init__(self, data_root: str | Path) -> None:
        self._root = Path(data_root) / "analysis"

    # -- public write / read ------------------------------------------------

    def write(
        self,
        symbol: str,
        angle_name: str,
        df: pd.DataFrame,
        *,
        analysis_from: int | None = None,
        analysis_until: int | None = None,
        run_id: str | None = None,
    ) -> str:
        """Write an angle's result DataFrame, auto-stamping fixed columns.

        Returns the run_id.
        """
        run_id = run_id or uuid4().hex[:12]
        started_at = datetime.now(timezone.utc)
        stored_at = started_at

        # stamp fixed columns
        df = df.copy()
        df["symbol"] = symbol
        df["angle_name"] = angle_name
        df["run_id"] = run_id
        df["started_at"] = pd.Timestamp(started_at)
        df["analysis_from"] = pd.Timestamp(analysis_from, unit="s", tz="UTC") if analysis_from else pd.NaT
        df["analysis_until"] = pd.Timestamp(analysis_until, unit="s", tz="UTC") if analysis_until else pd.NaT
        df["stored_at"] = pd.Timestamp(stored_at)

        path = self._path_for(symbol, angle_name, run_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(path, index=False)
        return run_id

    def read(self, symbol: str, angle_name: str, filters: Any = None) -> pd.DataFrame:
        """Read stored parquet files for a symbol+angle, with optional PyArrow filter pushdown."""
        angle_dir = self._root / symbol / angle_name
        files = sorted(angle_dir.glob("*.parquet")) if angle_dir.exists() else []
        if not files:
            return pd.DataFrame()
        dfs = [pq.read_table(f, filters=filters).to_pandas() for f in files]
        if not dfs:
            return pd.DataFrame()
        return pd.concat(dfs, ignore_index=True, sort=False)

    def read_latest(self, symbol: str, angle_name: str) -> pd.DataFrame:
        """Read only the most recent run for a symbol+angle."""
        files = self._list_files(symbol, angle_name)
        if not files:
            return pd.DataFrame()
        latest = max(files, key=lambda f: f.stat().st_mtime)
        return pq.read_table(latest).to_pandas()

    def list_angles(self, symbol: str) -> list[dict[str, Any]]:
        """List which angles have stored data for a symbol."""
        sym_dir = self._root / symbol
        if not sym_dir.exists():
            return []
        results = []
        for angle_dir in sorted(sym_dir.iterdir()):
            if not angle_dir.is_dir():
                continue
            files = list(angle_dir.glob("*.parquet"))
            if files:
                latest = max(files, key=lambda f: f.stat().st_mtime)
                meta = pq.read_metadata(latest)
                results.append({
                    "symbol": symbol,
                    "angle_name": angle_dir.name,
                    "run_count": len(files),
                    "latest_run": latest.stem,
                })
        return results

    def list_symbols(self) -> list[str]:
        """List all symbols that have stored data."""
        if not self._root.exists():
            return []
        return sorted(d.name for d in self._root.iterdir() if d.is_dir())

    # -- private helpers ----------------------------------------------------

    def _path_for(self, symbol: str, angle_name: str, run_id: str) -> Path:
        return self._root / symbol / angle_name / f"{run_id}.parquet"

    def _list_files(self, symbol: str, angle_name: str) -> list[Path]:
        d = self._root / symbol / angle_name
        if not d.exists():
            return []
        return sorted(d.glob("*.parquet"))
