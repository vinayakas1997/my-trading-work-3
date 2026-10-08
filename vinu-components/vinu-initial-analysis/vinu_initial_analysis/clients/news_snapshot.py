"""A frozen copy of one ticker's news for one time range, kept apart from the live news store.

The angles analyse a range of past news. Reading that range from the live store each time makes the result depend on whatever
the live store looked like at that moment (a revision, a re-index, a migration, an outage half-way through a 16-page read).
Here the range is read once, stored as a parquet file with a manifest, and reused, so the same input gives the same result.

    <data_root>/news_inputs/<SYMBOL>/<from>_<to>.parquet   the rows exactly as the news service returned them
    <data_root>/news_inputs/<SYMBOL>/<from>_<to>.json      manifest: when built, how many rows, data_through, schema version

`SnapshotNewsClient` has the same `get_ticker_news` as `NewsClient`, so the runner and every angle are unchanged and the rows
and columns they get are the same as before. A range that ended more than a day before it was built can no longer change and is
reused for good; a range that reaches the present is rebuilt when older than `LIVE_TTL_SEC`. An empty answer is never kept
(it could be an outage). Deleting a snapshot is always safe: it is rebuilt from the live store on the next use.
"""
from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path
from typing import Any, Callable

import pandas as pd

LOG = logging.getLogger(__name__)

SCHEMA_VERSION = 1
FINAL_GRACE_SEC = 86_400       # a range that ended this long before it was built is final
LIVE_TTL_SEC = 3_600           # a range that reaches the present is rebuilt after this long
_SAFE = re.compile(r"^[A-Z0-9][A-Z0-9.\-]{0,15}$")


def _symbol(symbol: str) -> str:
    s = (symbol or "").strip().upper()
    if not _SAFE.match(s):
        raise ValueError(f"not a ticker symbol: {symbol!r}")
    return s


def _plain(value: Any) -> Any:
    """Parquet hands back numpy values and NaN for missing; the angles were written against plain Python and None."""
    if hasattr(value, "tolist"):
        value = value.tolist()
    if isinstance(value, float) and value != value:
        return None
    if isinstance(value, list):
        return [_plain(v) for v in value]
    return value


def _records(df: pd.DataFrame) -> list[dict[str, Any]]:
    return [{k: _plain(v) for k, v in row.items()} for row in df.to_dict("records")]


class SnapshotNewsClient:
    def __init__(self, inner: Any, root: str | Path, *, clock: Callable[[], float] = time.time) -> None:
        self._inner = inner
        self.root = Path(root)
        self._clock = clock

    # -- same interface as NewsClient ------------------------------------------------------------------------------

    def get_articles_since(self, *a: Any, **k: Any) -> list[dict[str, Any]]:
        return self._inner.get_articles_since(*a, **k)

    def get_ticker_news(self, symbol: str, days: int = 7, *, from_ts: int | None = None, to_ts: int | None = None,
                        limit: int = 500) -> list[dict[str, Any]]:
        if from_ts is None:                      # a relative window ("the last N days") is not a range to freeze
            return self._inner.get_ticker_news(symbol, days, from_ts=from_ts, to_ts=to_ts, limit=limit)
        sym = _symbol(symbol)
        now = int(self._clock())
        end = int(to_ts) if to_ts is not None else now
        path = self._path(sym, int(from_ts), to_ts)
        manifest = self._manifest(path)
        if manifest and self._usable(manifest, end, now) and path.exists():
            return _records(pd.read_parquet(path))
        rows = self._inner.get_ticker_news(symbol, days, from_ts=from_ts, to_ts=to_ts, limit=limit)
        if rows:
            self._write(sym, int(from_ts), to_ts, end, rows, now)
        return rows

    # -- the snapshot files ----------------------------------------------------------------------------------------

    def _path(self, sym: str, from_ts: int, to_ts: int | None) -> Path:
        """A range that ends "now" keeps one file name, so it is rebuilt in place instead of piling up a file per call."""
        return self.root / sym / f"{from_ts}_{'now' if to_ts is None else int(to_ts)}.parquet"

    @staticmethod
    def _manifest(path: Path) -> dict[str, Any] | None:
        mp = path.with_suffix(".json")
        if not mp.exists():
            return None
        try:
            return json.loads(mp.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    @staticmethod
    def _usable(manifest: dict[str, Any], end: int, now: int) -> bool:
        if manifest.get("schema_version") != SCHEMA_VERSION:
            return False
        built = int(manifest.get("built_at", 0))
        if end <= built - FINAL_GRACE_SEC:
            return True                          # the range ended before it was built: it cannot change any more
        return now - built < LIVE_TTL_SEC

    def _write(self, sym: str, from_ts: int, to_ts: int | None, end: int, rows: list[dict[str, Any]], now: int) -> None:
        path = self._path(sym, from_ts, to_ts)
        path.parent.mkdir(parents=True, exist_ok=True)
        df = pd.DataFrame(rows)
        tmp = path.with_suffix(".tmp")
        df.to_parquet(tmp, index=False)
        tmp.replace(path)
        manifest = {
            "symbol": sym, "from_ts": from_ts, "to_ts": to_ts, "range_end": end, "built_at": now, "n_rows": len(rows),
            "data_through": max((int(r.get("sort_ts") or 0) for r in rows), default=0),
            "schema_version": SCHEMA_VERSION, "columns": list(df.columns), "source": "news-api /news/ticker",
        }
        path.with_suffix(".json").write_text(json.dumps(manifest), encoding="utf-8")

    # -- listing and deleting (the API the operator uses) ----------------------------------------------------------

    def list_snapshots(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        if not self.root.exists():
            return out
        for mp in sorted(self.root.glob("*/*.json")):
            try:
                out.append(json.loads(mp.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError):
                continue
        return out

    def delete(self, symbol: str) -> int:
        """Remove every snapshot of one ticker. Returns how many ranges were removed."""
        folder = self.root / _symbol(symbol)
        if not folder.exists():
            return 0
        n = len(list(folder.glob("*.json")))
        for p in folder.iterdir():
            p.unlink()
        folder.rmdir()
        return n
