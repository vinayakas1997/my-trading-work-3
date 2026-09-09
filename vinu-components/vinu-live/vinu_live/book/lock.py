"""Cross-process advisory lock for the shared trade-plan book.

The book (SQLite at ``<data_root>/trade_plan_book.db``) is written by more than
one process: the long-running trade-plan worker (``entrypoint.sh``) AND the
throwaway ``TradePlanOrchestrator`` the ``/live/trade-plan/*`` HTTP routes build
per request. Without a lock, two "read book -> decide -> write book" critical
sections (two reconciles, or an entry racing a reconcile) interleave and
double-apply a correction -- observed live: a reconcile that ``add_to_position``
the same delta twice, leaving the book at ~2x the broker before the next cycle
trimmed it back.

Same ``fcntl.flock`` / ``msvcrt.locking`` pattern as
``vinu-agent/vinu_agent/broker/kill_switch.py``'s ``kill_switch_lock()``. Hold it
only around the pure book read/decide/write -- never across an ``await`` on a
network call, so a slow broker can't stall the other process.
"""

from __future__ import annotations

import contextlib
import logging
import os
import sys
from pathlib import Path
from typing import Iterator

LOG = logging.getLogger(__name__)

# Set to a real path to lock; ":memory:" / "" / "off" disables (tests, in-memory
# books). Normally derived from the book db path by the orchestrator.
LOCK_PATH_ENV = "VINU_LIVE_BOOK_LOCK_PATH"


def lock_path_for_book(book_db_path: str | os.PathLike | None) -> str:
    """The lock path that goes with a book db path. In-memory / empty -> "off"."""
    s = str(book_db_path or "").strip()
    if not s or s == ":memory:" or s.startswith("file::memory:") or ":memory:" in s:
        return "off"
    return s + ".lock"


@contextlib.contextmanager
def book_lock(path: str | os.PathLike | None) -> Iterator[bool]:
    """Exclusive cross-process lock on ``path``. Yields True when the lock was
    actually held, False when locking was disabled or could not be set up
    (degrade to no-op rather than crash a trading cycle over a lock file)."""
    p = str(path or "").strip() or os.environ.get(LOCK_PATH_ENV, "").strip()
    if not p or p == "off" or p == ":memory:":
        yield False
        return
    lp = Path(p)
    try:
        lp.parent.mkdir(parents=True, exist_ok=True)
        if not lp.exists():
            lp.write_bytes(b"\0")
        f = open(lp, "r+b")
    except OSError as e:
        LOG.warning("book_lock: could not open %s (%s) -- proceeding without a lock", lp, e)
        yield False
        return
    try:
        if sys.platform == "win32":
            import msvcrt

            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl

            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            yield True
        finally:
            if sys.platform == "win32":
                import msvcrt

                f.seek(0)
                try:
                    msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
                except OSError:
                    pass
            else:
                import fcntl

                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    finally:
        f.close()
