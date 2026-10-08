"""Layer 1 of the news plan: every source's health is recorded, a failing source is switched off and retried, the operator can
switch any source off, and all of it is readable in plain words.

Why it exists: the AP feed answered http_403 on 252 of 252 polls and nobody was told, because the health rows had no reader
and nothing acted on them (data audit DA-N2)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from vinu_news.analysis.storage.repository import NewsRepository
from vinu_news.providers.registry import TickerNewsRegistry
from vinu_news.rss.fetch.fetch_result import FeedPollResult
from vinu_news.rss.storage.feed_health import update_feed_health
from vinu_news.sources.health import BACKOFF_SECONDS, SourceHealth, classify_error


class Clock:
    def __init__(self, t: float = 1_800_000_000.0) -> None:
        self.t = t

    def __call__(self) -> float:
        return self.t


@pytest.fixture
def repo(tmp_path: Path):
    r = NewsRepository(tmp_path / "health.db")
    yield r
    r.close()


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def health(repo, clock) -> SourceHealth:
    return SourceHealth(repo, now=clock, threshold=3)


def test_error_kinds_are_told_apart():
    assert classify_error("http_403") == "blocked"
    assert classify_error("http_404") == "gone"
    assert classify_error("http_429") == "rate_limited"
    assert classify_error("http_503") == "server_error"
    assert classify_error("timeout") == "timeout"
    assert classify_error("HTTPSConnectionPool: Failed to resolve host (name resolution)") == "network"
    assert classify_error("html_cloaking_detected") == "bad_content"
    assert classify_error(None) is None


def test_a_source_that_keeps_failing_is_switched_off_and_the_reason_is_kept(health):
    assert health.record("ap", ok=False, error="http_403") is None
    assert health.record("ap", ok=False, error="http_403") is None
    assert health.is_pollable("ap")
    assert health.record("ap", ok=False, error="http_403") == "switched_off"
    assert not health.is_pollable("ap")
    snap = {s["id"]: s for s in health.snapshot([{"id": "ap", "kind": "rss", "enabled": True}])}["ap"]
    assert snap["state"] == "off_automatic" and snap["error_kind"] == "blocked"
    assert "http_403" in snap["message"] and "blocked" in snap["message"]
    assert snap["message"] in health.attention([snap])


def test_the_retry_window_grows_and_a_success_switches_the_source_back_on(health, clock):
    for _ in range(3):
        health.record("ap", ok=False, error="http_403")
    assert not health.is_pollable("ap")
    clock.t += BACKOFF_SECONDS[0] + 1
    assert health.is_pollable("ap")                                   # one probe is allowed after 1 h
    assert health.record("ap", ok=False, error="http_403") == "switched_off"
    clock.t += BACKOFF_SECONDS[0] + 1
    assert not health.is_pollable("ap")                               # the second window is 6 h, not 1 h
    clock.t += BACKOFF_SECONDS[1]
    assert health.is_pollable("ap")
    assert health.record("ap", ok=True, articles=12) == "recovered"
    assert health.is_pollable("ap")
    row = health.snapshot([{"id": "ap", "kind": "rss", "enabled": True}])[0]
    assert row["state"] == "ok" and row["error_streak"] == 0 and row["off_count"] == 0 and row["last_error"] is None


def test_a_quiet_feed_with_no_error_is_never_switched_off(health):
    for _ in range(10):
        health.record("quiet", ok=True, articles=0)
    assert health.is_pollable("quiet")


def test_an_occasional_error_between_successes_does_not_switch_a_source_off(health):
    for _ in range(5):
        health.record("x", ok=False, error="timeout")
        health.record("x", ok=False, error="timeout")
        health.record("x", ok=True, articles=3)
    assert health.is_pollable("x")


def test_the_operator_switch_survives_and_turning_on_clears_an_automatic_switch_off(health):
    health.set_operator_off("cnbc", True)
    assert not health.is_pollable("cnbc")
    assert health.snapshot([{"id": "cnbc", "kind": "rss", "enabled": True}])[0]["state"] == "off_operator"
    for _ in range(3):
        health.record("ap", ok=False, error="http_403")
    health.set_operator_off("ap", False)
    assert health.is_pollable("ap")


def test_feeds_polled_by_the_rss_path_are_recorded_with_their_errors(repo):
    update_feed_health(repo, [
        FeedPollResult(feed_id="ap", url="u", status_code=403, articles=[], error="http_403", duration_ms=5),
        FeedPollResult(feed_id="cnbc", url="u", status_code=200, articles=[{"a": 1}], error=None, duration_ms=9),
        FeedPollResult(feed_id="sec", url="u", status_code=200, articles=[], error=None, duration_ms=7),
    ])
    snap = {s["id"]: s for s in SourceHealth(repo).snapshot(
        [{"id": i, "kind": "rss", "enabled": True} for i in ("ap", "cnbc", "sec")]
    )}
    assert snap["ap"]["state"] == "failing" and snap["ap"]["error_kind"] == "blocked"
    assert snap["cnbc"]["state"] == "ok" and snap["cnbc"]["last_articles"] == 1
    assert snap["sec"]["state"] == "ok" and snap["sec"]["last_articles"] == 0      # quiet, not failed


def test_an_old_health_table_gets_the_new_columns(tmp_path: Path):
    path = tmp_path / "old.db"
    c = sqlite3.connect(path)
    c.execute("CREATE TABLE feed_health (feed_id TEXT PRIMARY KEY, last_success_at INTEGER, last_failure_at INTEGER, "
              "fail_streak INTEGER NOT NULL DEFAULT 0, total_polls INTEGER NOT NULL DEFAULT 0, "
              "total_failures INTEGER NOT NULL DEFAULT 0, avg_latency_ms REAL NOT NULL DEFAULT 0, last_error TEXT)")
    c.execute("INSERT INTO feed_health (feed_id, fail_streak, total_polls, total_failures, last_error) "
              "VALUES ('ap_top_news', 252, 252, 252, 'http_403')")
    c.commit()
    c.close()
    r = NewsRepository(path)
    try:
        row = r.conn.execute("SELECT * FROM feed_health WHERE feed_id='ap_top_news'").fetchone()
        assert row["total_failures"] == 252 and row["operator_off"] == 0 and row["error_streak"] == 252   # real errors carry over
    finally:
        r.close()


class _Provider:
    def __init__(self, pid: str, fail: bool = False) -> None:
        self.provider_id = pid
        self.fail = fail
        self.calls = 0

    def is_configured(self) -> bool:
        return True

    def fetch_ticker_news(self, ticker, from_ts, to_ts):
        self.calls += 1
        if self.fail:
            raise RuntimeError("down")
        return [{"headline": "h", "link": f"https://x/{self.provider_id}"}]


def _registry(monkeypatch, health, providers):
    from vinu_news.providers import registry as reg

    class Cfg:
        def __init__(self, i):
            self.id, self.enabled, self.priority = i, True, 1

    monkeypatch.setattr(reg, "load_ticker_news_providers", lambda: [Cfg(p.provider_id) for p in providers])
    r = TickerNewsRegistry(health=health)
    r._providers = {p.provider_id: p for p in providers}
    return r


def test_providers_are_recorded_and_a_failing_one_is_skipped_once_switched_off(monkeypatch, health):
    good, bad = _Provider("good"), _Provider("bad", fail=True)
    registry = _registry(monkeypatch, health, [good, bad])
    for _ in range(3):
        items, errors = registry.fetch_for_ticker("AAPL", 0, 10)
        assert len(items) == 1 and errors == ["bad"]
    assert not health.is_pollable("bad") and health.is_pollable("good")
    calls = bad.calls
    items, errors = registry.fetch_for_ticker("AAPL", 0, 10)
    assert errors == [] and bad.calls == calls            # the switched-off provider is not called
    snap = {s["id"]: s for s in health.snapshot([{"id": "bad", "kind": "ticker_api", "enabled": True}])}["bad"]
    assert snap["kind"] == "ticker_api" and snap["state"] == "off_automatic"


@pytest.fixture
def client(tmp_path: Path):
    from vinu_news.server.app import create_app
    from vinu_news.service import NewsService
    from vinu_news.storage.sqlite_backend import SqliteBackend

    service = NewsService(storage=SqliteBackend(tmp_path / "api.db"))
    with TestClient(create_app(service=service)) as c:
        yield c
    service.close()


def test_the_sources_route_reads_out_every_feed_and_provider(client):
    body = client.get("/news/sources").json()
    ids = {s["id"]: s for s in body["sources"]}
    assert "alpaca" in ids and ids["alpaca"]["kind"] == "ticker_api"
    assert any(s["kind"] == "rss" for s in body["sources"])
    assert ids["yahoo"]["state"] == "off_config"
    assert set(body) >= {"sources", "counts", "attention"}


def test_the_operator_can_switch_a_source_off_and_on_through_the_api(client):
    off = client.patch("/news/sources/alpaca", json={"off": True})
    assert off.status_code == 200 and off.json()["state"] == "off_operator"
    assert client.get("/news/sources").json()["counts"]["off_operator"] == 1
    on = client.patch("/news/sources/alpaca", json={"off": False})
    assert on.json()["state"] != "off_operator"
    assert client.patch("/news/sources/no_such_source", json={"off": True}).status_code == 404


class _Rows(list):
    def fetchall(self):
        return list(self)


class _StaleColumns:
    """A connection that reports the column list from before another connection migrated: the race's exact view."""

    def __init__(self, conn, stale_columns):
        self._conn, self._stale = conn, stale_columns

    def execute(self, sql, *args):
        if sql.strip().upper().startswith("PRAGMA TABLE_INFO"):
            return _Rows([(0, name) for name in self._stale])
        return self._conn.execute(sql, *args)


def test_two_connections_migrating_at_once_do_not_fail(tmp_path: Path):
    """On first start two threads each opened a connection and both ran the ALTER; the loser died with 'duplicate column name'."""
    from vinu_news.sources.health import migrate

    path = tmp_path / "race.db"
    c1, c2 = sqlite3.connect(path), sqlite3.connect(path)
    c1.execute("CREATE TABLE feed_health (feed_id TEXT PRIMARY KEY, fail_streak INTEGER NOT NULL DEFAULT 0, last_error TEXT)")
    c1.commit()
    stale = ["feed_id", "fail_streak", "last_error"]
    migrate(c1)                                                      # the winner
    c1.commit()
    with pytest.raises(sqlite3.OperationalError, match="duplicate column name"):
        c2.execute("ALTER TABLE feed_health ADD COLUMN kind TEXT")     # what the loser used to do
    migrate(_StaleColumns(c2, stale))                                # now it carries on
    cols = {row[1] for row in c2.execute("PRAGMA table_info(feed_health)").fetchall()}
    assert {"kind", "error_streak", "operator_off", "auto_disabled_until"} <= cols
