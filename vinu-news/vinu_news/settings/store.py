"""Runtime settings bridge (mode, poll interval)."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Any

VALID_MODES = frozenset({"all", "ticker"})

DEFAULTS: dict[str, str] = {
    "mode": "ticker",
    "poll_interval_sec": "600",
}


@dataclass
class SettingsView:
    mode: str
    poll_interval_sec: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "poll_interval_sec": self.poll_interval_sec,
        }


class SettingsStore:
    """Read/write vinu_settings key-value store."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def init_schema(
        self,
        schema_sql: str,
        *,
        env_defaults: dict[str, str] | None = None,
    ) -> None:
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
        mode = data["mode"].lower()
        if mode not in VALID_MODES:
            mode = DEFAULTS["mode"]
        try:
            interval = int(data["poll_interval_sec"])
        except (TypeError, ValueError):
            interval = int(DEFAULTS["poll_interval_sec"])
        return SettingsView(mode=mode, poll_interval_sec=max(60, interval))

    def patch(self, *, mode: str | None = None, poll_interval_sec: int | None = None) -> SettingsView:
        if mode is not None:
            normalized = mode.lower()
            if normalized not in VALID_MODES:
                raise ValueError(f"mode must be one of {sorted(VALID_MODES)}")
            self._set("mode", normalized)
        if poll_interval_sec is not None:
            self._set("poll_interval_sec", str(max(60, poll_interval_sec)))
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
