"""Shared watchlist JSON file read/write (TASK-X01)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from vinu_stock.watchlist.store import WatchlistStore


def read_shared(path: Path) -> list[str]:
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    tickers = data.get("tickers") or []
    return [str(t).strip().upper() for t in tickers if str(t).strip()]


def write_shared(path: Path, tickers: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "tickers": sorted({t.strip().upper() for t in tickers if t.strip()}),
        "updated_at": int(datetime.now(timezone.utc).timestamp()),
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def sync_from_shared(store: WatchlistStore, path: Path) -> list[str]:
    """Merge shared tickers into local SQLite watchlist (union)."""
    shared = read_shared(path)
    if not shared:
        return []
    return store.add_tickers(shared)


def export_to_shared(store: WatchlistStore, path: Path) -> None:
    write_shared(path, store.list_tickers())
