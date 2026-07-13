"""Meta SQLite backend: catalog, settings, watchlist."""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

from vinu_stock.catalog.store import CatalogStore, open_catalog_db
from vinu_stock.config import settings_env_defaults
from vinu_stock.settings.store import SettingsStore, SettingsView
from vinu_stock.watchlist.store import WatchlistStore

_SCHEMA_DIR = Path(__file__).resolve().parent.parent


class MetaBackend:
    def __init__(self, meta_db_path: Path) -> None:
        self.meta_db_path = meta_db_path
        self._local = threading.local()
        conn = open_catalog_db(meta_db_path)
        try:
            self._init_schema(conn)
        finally:
            conn.close()

    def _init_schema(self, conn: sqlite3.Connection) -> None:
        CatalogStore(conn).init_schema(
            (_SCHEMA_DIR / "catalog" / "schema.sql").read_text(encoding="utf-8")
        )
        SettingsStore(conn).init_schema(
            (_SCHEMA_DIR / "settings" / "schema.sql").read_text(encoding="utf-8"),
            env_defaults=settings_env_defaults(),
        )
        WatchlistStore(conn).init_schema(
            (_SCHEMA_DIR / "watchlist" / "schema.sql").read_text(encoding="utf-8")
        )
        conn.commit()

    def _get_conn(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = open_catalog_db(self.meta_db_path)
            self._local.conn = conn
        return conn

    @property
    def catalog(self) -> CatalogStore:
        if not hasattr(self._local, "_catalog"):
            self._local._catalog = CatalogStore(self._get_conn())
        return self._local._catalog

    @property
    def settings(self) -> SettingsStore:
        if not hasattr(self._local, "_settings"):
            self._local._settings = SettingsStore(self._get_conn())
        return self._local._settings

    @property
    def watchlist(self) -> WatchlistStore:
        if not hasattr(self._local, "_watchlist"):
            self._local._watchlist = WatchlistStore(self._get_conn())
        return self._local._watchlist

    def close(self) -> None:
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            conn.close()

    def __enter__(self) -> MetaBackend:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def get_settings(self) -> SettingsView:
        return self.settings.get_all()

    def patch_settings(
        self,
        *,
        poll_interval_sec: int | None = None,
        default_provider: str | None = None,
        data_root: str | None = None,
    ) -> SettingsView:
        return self.settings.patch(
            poll_interval_sec=poll_interval_sec,
            default_provider=default_provider,
            data_root=data_root,
        )

    def get_watchlist(self) -> list[str]:
        return self.watchlist.list_tickers()

    def add_watchlist_tickers(self, tickers: list[str]) -> list[str]:
        return self.watchlist.add_tickers(tickers)

    def remove_watchlist_ticker(self, ticker: str) -> bool:
        return self.watchlist.remove_ticker(ticker)

    def health_info(self, data_root: Path) -> dict:
        symbols = self.catalog.list_symbols()
        return {
            "meta_db": str(self.meta_db_path),
            "data_root": str(data_root),
            "symbol_count": len(symbols),
            "watchlist_size": len(self.get_watchlist()),
        }
