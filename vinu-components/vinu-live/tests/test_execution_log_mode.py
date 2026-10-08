from __future__ import annotations

from vinu_live.execution_log import ExecutionLog


def test_orders_are_tagged_and_each_mode_sees_only_its_own(tmp_path, monkeypatch):
    log = ExecutionLog(tmp_path / "e.db")
    monkeypatch.setenv("VINU_ACCOUNT_MODE", "paper")
    log.record(symbol="AAA", side="buy", qty=1, outcome="submitted")
    monkeypatch.setenv("VINU_ACCOUNT_MODE", "real")
    monkeypatch.setenv("VINU_REAL_CAPITAL", "20")
    assert log.recent() == [] and log.bought_symbols() == set() and log.summary()["total"] == 0
    log.record(symbol="BBB", side="buy", qty=1, outcome="submitted")
    assert [r["symbol"] for r in log.recent()] == ["BBB"] and log.summary()["account_mode"] == "real"
    monkeypatch.setenv("VINU_ACCOUNT_MODE", "paper")
    assert [r["symbol"] for r in log.recent()] == ["AAA"] and log.bought_symbols() == {"AAA"}
    log.close()
