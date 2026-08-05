from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import uuid4

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

if TYPE_CHECKING:
    from vinu_initial_analysis.storage.meta import RunLog


FIXED_COLUMNS = ["symbol", "angle_name", "time_format", "run_id", "started_at", "analysis_from", "analysis_until", "stored_at"]

_MULTI_DIR = "_multi"


class AngleStorage:
    """Schema-agnostic parquet storage.

    Layout (see 03-storage-design.md section 6):
      single-ticker: {data_root}/analysis/{symbol}/{angle_name}/{granularity}/{tier}/{run_id}.parquet
      multi-ticker:  {data_root}/analysis/_multi/{ticker_hash}/{angle_name}/{granularity}/{tier}/{run_id}.parquet

    `granularity` is the bar resolution the angle operated on (e.g. "1D",
    "1H", "1min"), and `tier` is "tier2" (scheduled quarterly, the official
    immutable record) or "tier3" (triggered/ad-hoc, prunable). Physically
    separating tier2/tier3 into different path segments is what makes
    immutability of closed periods enforceable in code (see `_cleanup`)
    rather than just documented as a principle.

    Fixed metadata columns are auto-stamped — the angle only provides its data columns.
    """

    def __init__(self, data_root: str | Path, run_log: "RunLog | None" = None) -> None:
        self._root = Path(data_root) / "analysis"
        self._run_log = run_log

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
        granularity: str = "1D",
        tier: str = "tier2",
        tickers: list[str] | None = None,
    ) -> str:
        """Write an angle's result DataFrame, auto-stamping fixed columns.

        After writing, prunes the *tier3* files in this exact
        symbol/angle/granularity/tier bucket to at most *cleanup_max_runs*
        (oldest removed first). Set to 0 to disable. `tier2` writes are never
        pruned regardless of this cap — see `_cleanup` for why. Returns the
        run_id.

        granularity: the bar resolution this run operated on. Defaults to
        "1D" because none of today's 12 angles have a granularity concept yet
        (they consume whatever the price client returns) — this default keeps
        every existing call site working unchanged. Angles built with an
        actual granularity choice should pass it explicitly.

        tier: "tier2" (scheduled quarterly, the official immutable record) or
        "tier3" (triggered/ad-hoc, prunable). Defaults to "tier2" since all
        current angles run in a scheduled style, not an ad-hoc/triggered one.

        tickers: for multi-ticker methods that jointly analyze several
        tickers at once (none exist in this codebase yet — reserved for the
        32-method phase), pass the full ticker list to route this write under
        `_multi/{hash}/...` instead of `{symbol}/...`. The hash is computed
        over the sorted, uppercased, comma-joined ticker list (see
        `_ticker_hash`), so the same ticker set always hashes identically
        regardless of input order or case. When omitted, writes go under the
        single `symbol` as before.
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

        path = self._path_for(symbol, angle_name, run_id, granularity=granularity, tier=tier, tickers=tickers)
        path.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(path, index=False)

        if cleanup_max_runs > 0:
            self._cleanup(symbol, angle_name, cleanup_max_runs, granularity=granularity, tier=tier, tickers=tickers)

        return run_id

    def read(
        self,
        symbol: str,
        angle_name: str,
        filters: Any = None,
        *,
        granularity: str = "1D",
        tier: str = "tier2",
        tickers: list[str] | None = None,
    ) -> pd.DataFrame:
        """Read a symbol+angle's most recent run, with optional PyArrow filter pushdown.

        Up to `cleanup_max_runs` old tier3 runs are kept on disk for
        history/debugging, but only the latest is authoritative — older runs
        are superseded results for the same angle, not additional data
        points, so mixing them in would double-count events every time an
        angle gets re-run (Bug: previously concatenated every retained run,
        silently inflating counts like event_count/bearish/bullish on each
        re-run).

        granularity/tier default to "1D"/"tier2" — an exact match, not a
        wildcard, mirroring `write()`'s defaults and 03-storage-design.md
        section 7's resolve-latest query (which filters by exact granularity
        and tier, never scans across them). This keeps every existing
        call site's read symmetric with its write without any change.
        """
        path = self._resolve_latest_path(symbol, angle_name, granularity=granularity, tier=tier, tickers=tickers)
        if path is None:
            return pd.DataFrame()
        return pq.read_table(path, filters=filters).to_pandas()

    def read_latest(
        self,
        symbol: str,
        angle_name: str,
        *,
        granularity: str = "1D",
        tier: str = "tier2",
        tickers: list[str] | None = None,
    ) -> pd.DataFrame:
        """Read only the most recent run for a symbol+angle+granularity+tier."""
        path = self._resolve_latest_path(symbol, angle_name, granularity=granularity, tier=tier, tickers=tickers)
        if path is None:
            return pd.DataFrame()
        return pq.read_table(path).to_pandas()

    def _resolve_latest_path(
        self,
        symbol: str,
        angle_name: str,
        *,
        granularity: str = "1D",
        tier: str = "tier2",
        tickers: list[str] | None = None,
    ) -> Path | None:
        """Resolve the current run's file through the SQL run log, not by
        scanning the directory for the newest mtime.

        Picking "latest" by filesystem mtime is exactly the anti-pattern
        03-storage-design.md rules out (mtime survives copies/backfills/
        clock skew badly, and this codebase already had a double-counting
        bug traced back to trusting file listing order). When a RunLog is
        wired in, its `started_at`-ordered `completed`-only query — now also
        scoped by granularity/tier — is authoritative. The mtime scan is kept
        only as a fallback for the handful of call sites that construct a
        throwaway AngleStorage without a run_log (internal upstream-angle
        reads) — not because mtime is trusted, but so those sites don't
        regress to "no data" while they're incrementally wired up.

        Multi-ticker note: RunLog's schema keys runs by a single `symbol`
        column and has no ticker-hash key yet (that's future work alongside
        the 32 new multi-ticker methods this path segment is reserved for).
        So when `tickers` is given, we always use the mtime-scan fallback
        below rather than querying RunLog, same as the no-run_log case.
        """
        if self._run_log is not None and not tickers:
            run = self._run_log.get_latest_run(symbol, angle_name, granularity=granularity, tier=tier)
            if run is not None:
                candidate = self._path_for(
                    symbol, angle_name, run["run_id"], granularity=granularity, tier=tier, tickers=tickers
                )
                if candidate.is_file():
                    return candidate
        files = self._list_files(symbol, angle_name, granularity=granularity, tier=tier, tickers=tickers)
        if not files:
            return None
        return max(files, key=lambda f: f.stat().st_mtime)

    def list_angles(self, symbol: str) -> list[dict[str, Any]]:
        """List which angles have stored data for a symbol.

        Each angle's files now live nested under {granularity}/{tier}/, so
        run_count/latest_run are aggregated across all granularity/tier
        buckets for that angle — this is a summary API, and the smallest
        correct fix is "don't crash, keep counting every file" rather than
        exposing the new dimensions here too (nothing currently consumes a
        per-bucket breakdown).
        """
        sym_dir = self._root / symbol
        if not sym_dir.exists():
            return []
        results = []
        for angle_dir in sorted(sym_dir.iterdir()):
            if not angle_dir.is_dir():
                continue
            files = sorted(angle_dir.glob("*/*/*.parquet"))
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
        """List all symbols that have stored data.

        Excludes `_multi` — it holds multi-ticker joint results keyed by
        ticker-hash, not a real single ticker symbol, and callers of this
        method (CLI `status`/`compact_main --all`) treat every returned name
        as a ticker to loop over individually.
        """
        if not self._root.exists():
            return []
        return sorted(d.name for d in self._root.iterdir() if d.is_dir() and d.name != _MULTI_DIR)

    # -- private helpers ----------------------------------------------------

    @staticmethod
    def _ticker_hash(tickers: list[str]) -> str:
        """Deterministic short hash for a multi-ticker set.

        Computed over the sorted, uppercased, comma-joined ticker list so the
        same ticker set always hashes identically regardless of input order
        or case (e.g. ["msft", "AAPL"] and ["AAPL", "MSFT"] collide on purpose).
        """
        joined = ",".join(sorted(t.upper() for t in tickers))
        return hashlib.sha256(joined.encode()).hexdigest()[:12]

    def _angle_dir(self, symbol: str, angle_name: str, *, tickers: list[str] | None = None) -> Path:
        if tickers:
            return self._root / _MULTI_DIR / self._ticker_hash(tickers) / angle_name
        return self._root / symbol / angle_name

    def _path_for(
        self,
        symbol: str,
        angle_name: str,
        run_id: str,
        *,
        granularity: str = "1D",
        tier: str = "tier2",
        tickers: list[str] | None = None,
    ) -> Path:
        return self._angle_dir(symbol, angle_name, tickers=tickers) / granularity / tier / f"{run_id}.parquet"

    def _list_files(
        self,
        symbol: str,
        angle_name: str,
        *,
        granularity: str | None = None,
        tier: str | None = None,
        tickers: list[str] | None = None,
    ) -> list[Path]:
        """List parquet files for symbol+angle.

        When both `granularity` and `tier` are given, lists just that exact
        bucket (used internally by `_resolve_latest_path`/`_cleanup`, which
        always operate on one specific bucket). When either is omitted, lists
        across every granularity/tier bucket nested under the angle — this is
        what the summary APIs (`list_angles`) and existing tests (which don't
        know about the new dimensions) expect.
        """
        base = self._angle_dir(symbol, angle_name, tickers=tickers)
        if not base.exists():
            return []
        if granularity is not None and tier is not None:
            d = base / granularity / tier
            if not d.exists():
                return []
            return sorted(d.glob("*.parquet"))
        return sorted(base.glob("*/*/*.parquet"))

    def _cleanup(
        self,
        symbol: str,
        angle_name: str,
        max_runs: int,
        *,
        granularity: str = "1D",
        tier: str = "tier2",
        tickers: list[str] | None = None,
    ) -> int:
        """Delete oldest parquet files in this symbol/angle/granularity/tier
        bucket, keeping at most *max_runs* — but ONLY for tier3.

        `tier2` is the official scheduled-quarterly record and a core project
        principle is that closed periods must be immutable (see
        03-storage-design.md section 6) — pruning it would silently destroy
        the historical record. Physically separating tier2/tier3 into
        different path segments is what makes this enforceable here in code,
        not just documented: a tier2 write is simply never a candidate for
        deletion. `tier3` is triggered/ad-hoc and explicitly not the official
        record, so it's fine to cap on a rolling window.

        Returns the number of files deleted.
        """
        if tier == "tier2":
            return 0
        files = sorted(
            self._list_files(symbol, angle_name, granularity=granularity, tier=tier, tickers=tickers),
            key=lambda f: f.stat().st_mtime,
        )
        deleted = 0
        while len(files) > max_runs:
            files.pop(0).unlink()
            deleted += 1
        return deleted
