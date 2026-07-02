"""Runtime settings bridge (mode, poll interval)."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Any

VALID_MODES = frozenset({"all", "ticker"})
VALID_LLM_ANALYSIS_MODES = frozenset({"auto", "manual"})
VALID_TIERS = frozenset({1, 2, 3, 4})
DEFAULT_ACTIVE_TIERS = "1,2,3,4"

DEFAULTS: dict[str, str] = {
    "mode": "ticker",
    "poll_interval_sec": "600",
    "llm_analysis_mode": "auto",
    "llm_analysis_concurrency": "3",
    "active_tiers": DEFAULT_ACTIVE_TIERS,
}


def parse_active_tiers(raw: str) -> list[int]:
    """Parse comma-separated tier list; invalid tokens are skipped."""
    tiers: list[int] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            tier = int(part)
        except ValueError:
            continue
        if tier in VALID_TIERS and tier not in tiers:
            tiers.append(tier)
    return sorted(tiers) if tiers else sorted(VALID_TIERS)


def format_active_tiers(tiers: list[int]) -> str:
    normalized = sorted({t for t in tiers if t in VALID_TIERS})
    if not normalized:
        raise ValueError("active_tiers must include at least one tier from 1-4")
    return ",".join(str(t) for t in normalized)


@dataclass
class SettingsView:
    mode: str
    poll_interval_sec: int
    llm_analysis_mode: str
    llm_analysis_concurrency: int
    active_tiers: list[int]

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "poll_interval_sec": self.poll_interval_sec,
            "llm_analysis_mode": self.llm_analysis_mode,
            "llm_analysis_concurrency": self.llm_analysis_concurrency,
            "active_tiers": self.active_tiers,
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
        llm_analysis_mode = data["llm_analysis_mode"].lower()
        if llm_analysis_mode not in VALID_LLM_ANALYSIS_MODES:
            llm_analysis_mode = DEFAULTS["llm_analysis_mode"]
        try:
            concurrency = int(data["llm_analysis_concurrency"])
        except (TypeError, ValueError):
            concurrency = int(DEFAULTS["llm_analysis_concurrency"])
        active_tiers = parse_active_tiers(data.get("active_tiers", DEFAULT_ACTIVE_TIERS))
        return SettingsView(
            mode=mode,
            poll_interval_sec=max(60, interval),
            llm_analysis_mode=llm_analysis_mode,
            llm_analysis_concurrency=max(1, min(20, concurrency)),
            active_tiers=active_tiers,
        )

    def patch(
        self,
        *,
        mode: str | None = None,
        poll_interval_sec: int | None = None,
        llm_analysis_mode: str | None = None,
        llm_analysis_concurrency: int | None = None,
        active_tiers: list[int] | None = None,
    ) -> SettingsView:
        if mode is not None:
            normalized = mode.lower()
            if normalized not in VALID_MODES:
                raise ValueError(f"mode must be one of {sorted(VALID_MODES)}")
            self._set("mode", normalized)
        if poll_interval_sec is not None:
            self._set("poll_interval_sec", str(max(60, poll_interval_sec)))
        if llm_analysis_mode is not None:
            normalized_llm_mode = llm_analysis_mode.lower()
            if normalized_llm_mode not in VALID_LLM_ANALYSIS_MODES:
                raise ValueError(
                    f"llm_analysis_mode must be one of {sorted(VALID_LLM_ANALYSIS_MODES)}"
                )
            self._set("llm_analysis_mode", normalized_llm_mode)
        if llm_analysis_concurrency is not None:
            self._set("llm_analysis_concurrency", str(max(1, min(20, llm_analysis_concurrency))))
        if active_tiers is not None:
            self._set("active_tiers", format_active_tiers(active_tiers))
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
