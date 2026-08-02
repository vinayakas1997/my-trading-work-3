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
        cleanup_max_runs: int = 10,
    ) -> str:
        """Write an angle's result DataFrame, auto-stamping fixed columns.

        After writing, prunes the angle's parquet directory to at most
        *cleanup_max_runs* files (oldest removed first).  Set to 0 to disable.
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

        if cleanup_max_runs > 0:
            self._cleanup(symbol, angle_name, cleanup_max_runs)

        return run_id

    def read(self, symbol: str, angle_name: str, filters: Any = None) -> pd.DataFrame:
        """Read a symbol+angle's most recent run, with optional PyArrow filter pushdown.

        Up to `cleanup_max_runs` old runs are kept on disk for history/debugging,
        but only the latest is authoritative — older runs are superseded results
        for the same angle, not additional data points, so mixing them in would
        double-count events every time an angle gets re-run (Bug: previously
        concatenated every retained run, silently inflating counts like
        event_count/bearish/bullish on each re-run).
        """
        files = self._list_files(symbol, angle_name)
        if not files:
            return pd.DataFrame()
        latest = max(files, key=lambda f: f.stat().st_mtime)
        return pq.read_table(latest, filters=filters).to_pandas()

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

    def _cleanup(self, symbol: str, angle_name: str, max_runs: int) -> int:
        """Delete oldest parquet files for *symbol/angle_name*, keeping at most *max_runs*.

        Returns the number of files deleted.
        """
        files = sorted(self._list_files(symbol, angle_name), key=lambda f: f.stat().st_mtime)
        deleted = 0
        while len(files) > max_runs:
            files.pop(0).unlink()
            deleted += 1
        return deleted
