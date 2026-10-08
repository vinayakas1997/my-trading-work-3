"""Source health: one place that knows, for every news source, whether it works, why not, and whether to poll it.

A source is an RSS feed or a ticker-news API provider (Alpaca, FMP, Yahoo). Layer 1 of the news plan
(Proper-Project-Implementation/07-news-layers/plan.md):

* every poll outcome is recorded with an error kind (blocked, gone, rate_limited, timeout, network, server, other);
* after `auto_off_after` errors in a row a source is switched off automatically and retried later (1 h, 6 h, then 24 h);
* the operator can switch any source off; that switch lives in the database (the packaged yaml is read-only in the
  container, so a yaml toggle cannot persist);
* `snapshot()` reads all of it out in plain words, and a state change is logged.

An empty answer with no error is not an error: a quiet feed is normal. Only errors count toward switching a source off.
"""
from __future__ import annotations

import logging
import os
import sqlite3
import time
from datetime import datetime, timezone
from typing import Any, Callable

LOG = logging.getLogger(__name__)

DEFAULT_AUTO_OFF_AFTER = 10
BACKOFF_SECONDS = (3_600, 21_600, 86_400)   # 1 h, 6 h, then 24 h for every further failed retry

KIND_RSS = "rss"
KIND_API = "ticker_api"

_NEW_COLUMNS = (
    ("kind", "TEXT NOT NULL DEFAULT 'rss'"),
    ("error_kind", "TEXT"),
    ("error_streak", "INTEGER NOT NULL DEFAULT 0"),
    ("off_count", "INTEGER NOT NULL DEFAULT 0"),
    ("auto_disabled_until", "INTEGER"),
    ("operator_off", "INTEGER NOT NULL DEFAULT 0"),
    ("last_articles", "INTEGER"),
)


def auto_off_after() -> int:
    raw = (os.getenv("VINU_NEWS_SOURCE_AUTO_OFF_AFTER") or "").strip()
    try:
        value = int(raw) if raw else DEFAULT_AUTO_OFF_AFTER
    except ValueError:
        value = DEFAULT_AUTO_OFF_AFTER
    return max(1, value)


def classify_error(error: str | None) -> str | None:
    """A short kind for an error text, so a reader can tell 'blocked' from 'down' without parsing strings."""
    if not error:
        return None
    e = str(error).lower()
    if "http_429" in e or "429" in e and "http" in e:
        return "rate_limited"
    if "http_401" in e or "http_403" in e or "forbidden" in e or "unauthor" in e:
        return "blocked"
    if "http_404" in e or "http_410" in e:
        return "gone"
    if "http_5" in e or " 500" in e or " 502" in e or " 503" in e or " 504" in e:
        return "server_error"
    if "timeout" in e or "timed out" in e:
        return "timeout"
    if "name resolution" in e or "connection" in e or "unreachable" in e or "dns" in e:
        return "network"
    if "html_cloaking" in e or "empty_body" in e or "body_too_short" in e or "parse" in e:
        return "bad_content"
    return "other"


def _utc(ts: int | float | None) -> str | None:
    if ts is None:
        return None
    return datetime.fromtimestamp(float(ts), tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def migrate(conn: Any) -> None:
    """Add the layer-1 columns to an existing `feed_health` table. Safe when two threads open their own connections at
    the same moment (the second `ALTER` finds the column already there: seen as 'duplicate column name' on first start)."""
    existing = {row[1] for row in conn.execute("PRAGMA table_info(feed_health)").fetchall()}
    added_error_streak = False
    for name, definition in _NEW_COLUMNS:
        if name in existing:
            continue
        try:
            conn.execute(f"ALTER TABLE feed_health ADD COLUMN {name} {definition}")
        except sqlite3.OperationalError as exc:
            if "duplicate column name" not in str(exc):
                raise
            continue
        if name == "error_streak":
            added_error_streak = True
    if added_error_streak:
        # The old counter also counted quiet feeds as failures (last_error 'empty_feed'); real errors in a row carry over,
        # so a source that was already failing every poll is switched off at its next poll instead of ten polls later.
        conn.execute(
            "UPDATE feed_health SET error_streak = fail_streak "
            "WHERE last_error IS NOT NULL AND last_error != 'empty_feed'"
        )


class SourceHealth:
    """Reads and writes the `feed_health` table (one row per source) through a news repository."""

    def __init__(self, repo: Any, *, now: Callable[[], float] = time.time, threshold: int | None = None) -> None:
        self._repo = repo
        self._now = now
        self._threshold = threshold

    @property
    def threshold(self) -> int:
        return self._threshold if self._threshold is not None else auto_off_after()

    def _row(self, source_id: str) -> Any:
        return self._repo.conn.execute("SELECT * FROM feed_health WHERE feed_id = ?", (source_id,)).fetchone()

    def is_pollable(self, source_id: str) -> bool:
        row = self._row(source_id)
        if row is None:
            return True
        if row["operator_off"]:
            return False
        until = row["auto_disabled_until"]
        return not (until and until > self._now())

    def record(
        self,
        source_id: str,
        *,
        ok: bool,
        error: str | None = None,
        kind: str = KIND_RSS,
        duration_ms: float = 0,
        articles: int | None = None,
    ) -> str | None:
        """Write one poll outcome. Returns 'switched_off' or 'recovered' when the source changed state, else None."""
        now = int(self._now())
        row = self._row(source_id)
        total_polls = (row["total_polls"] if row else 0) + 1
        total_failures = row["total_failures"] if row else 0
        fail_streak = row["fail_streak"] if row else 0
        error_streak = row["error_streak"] if row else 0
        off_count = row["off_count"] if row else 0
        avg_latency = row["avg_latency_ms"] if row else 0.0
        last_success = row["last_success_at"] if row else None
        last_failure = row["last_failure_at"] if row else None
        operator_off = row["operator_off"] if row else 0
        until = row["auto_disabled_until"] if row else None
        last_error = row["last_error"] if row else None
        error_kind = row["error_kind"] if row else None
        was_off = bool(row and row["error_streak"] >= self.threshold)

        avg_latency = (avg_latency * (total_polls - 1) + float(duration_ms or 0)) / total_polls
        event: str | None = None
        if ok:
            fail_streak = error_streak = off_count = 0
            until = None
            last_error = error_kind = None
            last_success = now
            if was_off:
                event = "recovered"
        else:
            total_failures += 1
            fail_streak += 1
            error_streak += 1
            last_failure = now
            last_error = (error or "error")[:300]
            error_kind = classify_error(last_error)
            if error_streak >= self.threshold:
                step = min(off_count, len(BACKOFF_SECONDS) - 1)
                until = now + BACKOFF_SECONDS[step]
                off_count += 1
                event = "switched_off"

        with self._repo.conn:
            self._repo.conn.execute(
                """
                INSERT INTO feed_health (feed_id, last_success_at, last_failure_at, fail_streak, total_polls,
                    total_failures, avg_latency_ms, last_error, kind, error_kind, error_streak, off_count,
                    auto_disabled_until, operator_off, last_articles)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(feed_id) DO UPDATE SET
                    last_success_at = excluded.last_success_at, last_failure_at = excluded.last_failure_at,
                    fail_streak = excluded.fail_streak, total_polls = excluded.total_polls,
                    total_failures = excluded.total_failures, avg_latency_ms = excluded.avg_latency_ms,
                    last_error = excluded.last_error, kind = excluded.kind, error_kind = excluded.error_kind,
                    error_streak = excluded.error_streak, off_count = excluded.off_count,
                    auto_disabled_until = excluded.auto_disabled_until, last_articles = excluded.last_articles
                """,
                (source_id, last_success, last_failure, fail_streak, total_polls, total_failures, avg_latency,
                 last_error, kind, error_kind, error_streak, off_count, until, operator_off, articles),
            )
        if event == "switched_off":
            LOG.warning(
                "news source %s switched off automatically after %d errors in a row (%s: %s); next try %s",
                source_id, error_streak, error_kind, last_error, _utc(until),
            )
        elif event == "recovered":
            LOG.info("news source %s works again; switched back on", source_id)
        return event

    def set_operator_off(self, source_id: str, off: bool, *, kind: str = KIND_RSS) -> None:
        """The operator's switch. Turning a source back on also clears an automatic switch-off so it is tried at once."""
        with self._repo.conn:
            self._repo.conn.execute(
                "INSERT INTO feed_health (feed_id, kind, operator_off) VALUES (?, ?, ?) "
                "ON CONFLICT(feed_id) DO UPDATE SET operator_off = excluded.operator_off",
                (source_id, kind, 1 if off else 0),
            )
            if not off:
                self._repo.conn.execute(
                    "UPDATE feed_health SET auto_disabled_until = NULL, error_streak = 0, off_count = 0 WHERE feed_id = ?",
                    (source_id,),
                )

    def snapshot(self, configured: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Every source with its state and a sentence. `configured` rows: {id, kind, enabled, ...extra}. Sources that
        have health rows but are no longer configured are listed too (state `not_configured`)."""
        now = self._now()
        rows = {r["feed_id"]: r for r in self._repo.conn.execute("SELECT * FROM feed_health").fetchall()}
        out: list[dict[str, Any]] = []
        seen: set[str] = set()
        for cfg in configured:
            seen.add(cfg["id"])
            out.append(self._describe(cfg, rows.get(cfg["id"]), now))
        for sid, row in rows.items():
            if sid not in seen:
                out.append(self._describe({"id": sid, "kind": row["kind"], "enabled": False, "configured": False}, row, now))
        return out

    def _describe(self, cfg: dict[str, Any], row: Any, now: float) -> dict[str, Any]:
        sid = cfg["id"]
        d: dict[str, Any] = dict(cfg)
        d["kind"] = cfg.get("kind") or (row["kind"] if row else KIND_RSS)
        d["configured"] = cfg.get("configured", True)
        d.update(
            operator_off=bool(row["operator_off"]) if row else False,
            error_streak=row["error_streak"] if row else 0,
            off_count=row["off_count"] if row else 0,
            auto_disabled_until=row["auto_disabled_until"] if row else None,
            last_success_at=row["last_success_at"] if row else None,
            last_failure_at=row["last_failure_at"] if row else None,
            last_error=row["last_error"] if row else None,
            error_kind=row["error_kind"] if row else None,
            total_polls=row["total_polls"] if row else 0,
            total_failures=row["total_failures"] if row else 0,
            avg_latency_ms=round(row["avg_latency_ms"], 1) if row else 0.0,
            last_articles=row["last_articles"] if row else None,
        )
        until = d["auto_disabled_until"]
        if not d["configured"]:
            d["state"], d["message"] = "not_configured", f"{sid}: has history but is no longer configured"
        elif d["operator_off"]:
            d["state"], d["message"] = "off_operator", f"{sid}: switched off by the operator"
        elif until and until > now:
            d["state"] = "off_automatic"
            d["message"] = (
                f"{sid}: switched off automatically until {_utc(until)} after {d['error_streak']} errors in a row "
                f"({d['error_kind']}: {d['last_error']})"
            )
        elif not cfg.get("enabled", True):
            d["state"], d["message"] = "off_config", f"{sid}: disabled in the configuration"
        elif d["error_streak"] > 0:
            d["state"] = "failing"
            d["message"] = f"{sid}: last {d['error_streak']} poll(s) failed ({d['error_kind']}: {d['last_error']})"
        elif d["total_polls"] == 0:
            d["state"], d["message"] = "never_polled", f"{sid}: not polled yet"
        else:
            d["state"], d["message"] = "ok", f"{sid}: working"
        return d

    @staticmethod
    def attention(snapshot: list[dict[str, Any]]) -> list[str]:
        """The sources a person should look at, in plain words: failing or automatically switched off."""
        return [s["message"] for s in snapshot if s["state"] in ("failing", "off_automatic")]
