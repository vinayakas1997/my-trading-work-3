"""Shared per-ticker JSON profile files -- one file per symbol, written
by multiple independent services, each owning exactly one top-level key.

Mirrors vinu-stock-price's `vinu_stock/watchlist/shared.py` (FileLock +
tmp-file-then-atomic-rename) with one difference: that module always
overwrites the whole file (one writer, one flat list); this one does a
read-modify-write under lock, since several unrelated services each own
a different key in the same file and must never clobber each other's.

Best-effort throughout, same contract as `calibration_log.py`'s
`record()`: a write here must never be able to break a real caller's
actual work (a backfill job, an angle backtest, a screener scan). Any
failure -- missing/unwritable shared root, lock timeout, a
non-serializable value -- is swallowed, never raised.

Ships inert: when `shared_root` is None or doesn't resolve to a real,
writable directory, every write is a silent no-op and every read
returns {} -- no config means zero behavior change for any caller.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from filelock import FileLock


def _profile_path(shared_root: Path, symbol: str) -> Path:
    return shared_root / "ticker-profiles" / f"{symbol.strip().upper()}.json"


def _lock_path(path: Path) -> Path:
    return path.with_suffix(path.suffix + ".lock")


def read_ticker_profile(shared_root: Path | str | None, symbol: str) -> dict[str, Any]:
    """Best-effort read of one ticker's full profile (all services'
    keys). Missing file, missing shared_root, or corrupt JSON all
    return {} -- never raises."""
    if not shared_root:
        return {}
    try:
        path = _profile_path(Path(shared_root), symbol)
        if not path.is_file():
            return {}
        lock = FileLock(str(_lock_path(path)), preserve_lock_file=True)
        with lock:
            data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:  # noqa: BLE001 -- best-effort, see module docstring
        return {}


def write_ticker_profile_key(
    shared_root: Path | str | None,
    symbol: str,
    service_key: str,
    data: dict[str, Any],
) -> None:
    """Read-modify-write under FileLock: read the existing profile (or
    start fresh), replace ONLY `data[service_key]`, write back via
    tmp-file + atomic rename. Every other service's key in the file is
    left untouched.

    Caller contract for nested data (e.g. one service writing facts for
    several sub-items under its own key, like per-angle results): this
    function replaces `service_key` wholesale, it does not merge inside
    it. A caller that needs to preserve prior nested entries must read
    the current value first (`read_ticker_profile(...).get(service_key,
    {})`), merge in its update, and pass the merged dict here.

    Best-effort: any failure (missing/unwritable shared_root, lock
    timeout, non-serializable value in `data`) is swallowed, never
    raised -- see module docstring."""
    if not shared_root:
        return
    try:
        path = _profile_path(Path(shared_root), symbol)
        path.parent.mkdir(parents=True, exist_ok=True)
        lock = FileLock(str(_lock_path(path)), preserve_lock_file=True)
        with lock:
            try:
                current = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
                if not isinstance(current, dict):
                    current = {}
            except (json.JSONDecodeError, OSError):
                current = {}
            current["symbol"] = symbol.strip().upper()
            current[service_key] = {**data, "updated_at": time.time()}
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(current, indent=2, default=str), encoding="utf-8")
            tmp.replace(path)
    except Exception:  # noqa: BLE001 -- best-effort, see module docstring
        pass
