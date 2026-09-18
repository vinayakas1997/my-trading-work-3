"""Torch-free reader for vinu-initial-analysis's Parquet tree -- the real
fix behind analyses Q and N (missing-pieces-of-system/maturity-agentic-
system/thinking-1/02-decided-pattern/25-A-Y-details/07-implementation-
plan-status.md's "Q and N, re-investigated 2026-09-20" note).

Both Q and N were filed as "dependency-cost deferrals" because
vinu-initial-analysis declares torch/xgboost/chronos-forecasting/timesfm
as base (non-optional) `dependencies` in its pyproject.toml -- installing
that package, the way every other analyst in this worker mount-and-
imports its source service, really would drag all of that in. But *this*
module never imports `vinu_initial_analysis` at all: `AngleStorage`
(`vinu_initial_analysis/storage/parquet.py`) -- the class that actually
writes/reads these files in production -- only ever imports
pandas/pyarrow itself to do it. Both are already installed here
transitively (pandas via vinu-research, pyarrow via vinu-stock-price), so
reading the same on-disk layout directly costs nothing new.

Layout mirrored from `AngleStorage` (single-ticker only -- Q/N never need
the `_multi` joint-analysis path):
  {data_root}/analysis/{symbol}/{angle_name}/{granularity}/{tier}/{run_id}.parquet

Only the LATEST run per (symbol, angle_name, granularity, tier) is read,
never every run concatenated -- `AngleStorage.read()`'s own docstring
explains why: each new run (particularly a `tier2` quarterly recompute)
recomputes the FULL series from vinu-initial-analysis's own fixed start
date through the new period end, so older runs are strict subsets of the
latest one. Concatenating them would double- (or N-times-) count every
older row. "Latest" here is by file mtime, same fallback `AngleStorage`
itself uses for call sites without a `RunLog` wired in -- this module has
no `RunLog`/duckdb access either, by design (pure filesystem + pyarrow).
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow.parquet as pq

_MULTI_DIR = "_multi"


def to_utc_datetime(value: Any) -> datetime | None:
    """Normalizes a `stored_at`/`analysis_at`-shaped value (read back from
    Parquet) to a tz-aware UTC `datetime`, or None if it can't be parsed.

    `AngleStorage.write()` stamps `stored_at` from `datetime.now(timezone.
    utc)`, but whether pyarrow round-trips that as tz-aware or tz-naive
    depends on the exact write path -- comparing a tz-naive pandas
    Timestamp against a tz-aware `datetime` raises, so every caller here
    normalizes through this one function instead of comparing raw values
    directly.
    """
    if value is None:
        return None
    try:
        ts = pd.Timestamp(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(ts):
        return None
    if ts.tzinfo is None:
        return ts.to_pydatetime().replace(tzinfo=timezone.utc)
    return ts.tz_convert("UTC").to_pydatetime()


def list_analyzed_symbols(data_root: Path) -> list[str]:
    """Every symbol with at least one stored analysis run -- mirrors
    `AngleStorage.list_symbols()` exactly (same exclusion of `_multi`),
    without importing it."""
    root = Path(data_root) / "analysis"
    if not root.exists():
        return []
    return sorted(d.name for d in root.iterdir() if d.is_dir() and d.name != _MULTI_DIR)


def read_latest_run(
    data_root: Path,
    symbol: str,
    angle_name: str,
    *,
    granularity: str = "1D",
    tier: str = "tier2",
) -> pd.DataFrame:
    """The latest stored run's full row set for (symbol, angle_name,
    granularity, tier), or an empty DataFrame when nothing is stored yet.
    Never raises on a malformed/partially-written file -- returns empty
    for that run instead, same fail-open posture every other analyst
    here already uses for its own store reads.

    Use this for angles whose *single* latest run already contains a
    full walk-forward history (one row per backtest step, e.g. the DL
    angles Q reads) -- reading every run and concatenating would
    double-count, see module docstring.
    """
    base = Path(data_root) / "analysis" / symbol / angle_name / granularity / tier
    if not base.exists():
        return pd.DataFrame()
    files = sorted(base.glob("*.parquet"))
    if not files:
        return pd.DataFrame()
    latest = max(files, key=lambda f: f.stat().st_mtime)
    try:
        return pq.read_table(latest).to_pandas()
    except Exception:
        return pd.DataFrame()


def read_all_runs(
    data_root: Path,
    symbol: str,
    angle_name: str,
    *,
    granularity: str = "1D",
    tier: str = "tier2",
) -> pd.DataFrame:
    """Every stored run for (symbol, angle_name, granularity, tier),
    concatenated and sorted oldest-first by `stored_at` (a fixed metadata
    column `AngleStorage.write()` always stamps, regardless of the
    angle's own schema).

    Use this for angles whose `compute()` returns a single "as of now"
    snapshot row per invocation (e.g. shock_personality/shock_clustering,
    which N reads) -- unlike the DL angles' walk-forward series, here
    each run genuinely is one new, non-overlapping data point, so
    concatenating across runs is the real history, not double-counting.
    """
    base = Path(data_root) / "analysis" / symbol / angle_name / granularity / tier
    if not base.exists():
        return pd.DataFrame()
    frames = []
    for path in sorted(base.glob("*.parquet")):
        try:
            frames.append(pq.read_table(path).to_pandas())
        except Exception:
            continue
    if not frames:
        return pd.DataFrame()
    df = pd.concat(frames, ignore_index=True)
    if "stored_at" in df.columns:
        df = df.sort_values("stored_at").reset_index(drop=True)
    return df
