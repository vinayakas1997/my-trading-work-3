"""One news database per ticker (the same style as the price folders).

While Alpaca is the only source, news is fetched per ticker, so each ticker owns a self-contained dataset: its own file
`<root>/<SYMBOL>.db` with every layer of the news plan inside (items, stories, facts, the ticker table). Adding a ticker creates
a file, removing one deletes it, prefilling one never takes a write lock that live writes for the other tickers need, and a
migration or rebuild touches one small file. A story that mentions two tickers is stored in both files with the same article
id (deliberate: each file means "what the feed says about X").

The central database keeps only what is not about one ticker: settings, the watchlist, backfill state and source health.
"""
from __future__ import annotations

import logging
import re
import threading
import time
from pathlib import Path

from vinu_news.storage.sqlite_backend import SqliteBackend

LOG = logging.getLogger(__name__)
_SAFE = re.compile(r"^[A-Z0-9][A-Z0-9.\-]{0,15}$")


def clean_ticker(ticker: str) -> str:
    t = (ticker or "").strip().upper()
    if not _SAFE.match(t):
        raise ValueError(f"not a ticker symbol: {ticker!r}")
    return t


class TickerStores:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._stores: dict[str, SqliteBackend] = {}
        self._lock = threading.Lock()

    def path(self, ticker: str) -> Path:
        return self.root / f"{clean_ticker(ticker)}.db"

    def get(self, ticker: str) -> SqliteBackend:
        t = clean_ticker(ticker)
        with self._lock:
            store = self._stores.get(t)
            if store is None:
                store = SqliteBackend(self.root / f"{t}.db", seed_reference=False)
                self._stores[t] = store
            return store

    def exists(self, ticker: str) -> bool:
        return self.path(ticker).exists()

    def tickers(self) -> list[str]:
        """Every ticker that has a file (not only the ones opened in this process)."""
        return sorted(p.stem for p in self.root.glob("*.db") if _SAFE.match(p.stem))

    def drop(self, ticker: str) -> bool:
        """Remove a ticker's whole dataset: close it and delete its files. False when there was none."""
        t = clean_ticker(ticker)
        with self._lock:
            store = self._stores.pop(t, None)
        if store is not None:
            store.close()      # note: a connection opened by another thread cannot be closed from here (sqlite's thread check)
        store = None
        import gc

        gc.collect()           # ...so drop the last references and let the unreferenced connections finalise
        removed = False
        for suffix in ("", "-wal", "-shm"):
            p = self.root / f"{t}.db{suffix}"
            for attempt in range(10):
                if not p.exists():
                    break
                try:
                    p.unlink()
                    removed = suffix == "" or removed
                    break
                except PermissionError:
                    gc.collect()
                    # a worker thread still had the file open (Windows refuses to delete an open file); let it finish
                    if attempt == 9:
                        raise
                    time.sleep(0.2)
        if removed:
            LOG.info("dropped the news dataset of %s", t)
        return removed

    def close(self) -> None:
        with self._lock:
            stores, self._stores = list(self._stores.values()), {}
        for s in stores:
            try:
                s.close()
            except Exception:  # noqa: BLE001
                LOG.warning("could not close a ticker store", exc_info=True)
