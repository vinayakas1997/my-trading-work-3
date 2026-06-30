"""Runtime settings (poll interval, default provider, data root)."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Any

DEFAULTS: dict[str, str] = {
    "poll_interval_sec": "60",
    "default_provider": "polygon",
    "data_root": "./data",
}


@dataclass
class SettingsView:
    poll_interval_sec: int
    default_provider: str
    data_root: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "poll_interval_sec": self.poll_interval_sec,
            "default_provider": self.default_provider,
            "data_root": self.data_root,
        }


class SettingsStore:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def init_schema(self, schema_sql: str, *, env_defaults: dict[str, str] | None = None) -> None:
        self._conn.executescript(schema_sql)
        defaults = {**DEFAULTS, **(env_defaults or {})}
        for key, value in defaults.items():
            self._conn.execute(
                "INSERT OR IGNORE INTO vinu_settings (key, value) VALUES (?, ?)",
                (key, value),
            )

    def get_all(self) -> SettingsView:
        rows = self._conn.execute("SELECT key, value FROM vinu_settings").fetchall()
        data = dict(DEFAULTS)
        data.update({row["key"]: row["value"] for row in rows})
        try:
            interval = int(data["poll_interval_sec"])
        except (TypeError, ValueError):
            interval = int(DEFAULTS["poll_interval_sec"])
        return SettingsView(
            poll_interval_sec=max(10, interval),
            default_provider=data.get("default_provider", DEFAULTS["default_provider"]),
            data_root=data.get("data_root", DEFAULTS["data_root"]),
        )

    def patch(
        self,
        *,
        poll_interval_sec: int | None = None,
        default_provider: str | None = None,
        data_root: str | None = None,
    ) -> SettingsView:
        if poll_interval_sec is not None:
            self._set("poll_interval_sec", str(max(10, poll_interval_sec)))
        if default_provider is not None:
            self._set("default_provider", default_provider.strip().lower())
        if data_root is not None:
            self._set("data_root", data_root.strip())
        self._conn.commit()
        return self.get_all()

    def _set(self, key: str, value: str) -> None:
        self._conn.execute(
            """
            INSERT INTO vinu_settings (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, value),
        )
