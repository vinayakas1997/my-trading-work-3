"""Contract: every trade-audit entry says which money it was made under.

The log's `paper_trading` flag defaulted to False and nobody passed True, so a paper stack wrote 1,289 entries on 2026-10-08
that all said real trading, and nothing in the file carried the paper/real tag the rest of the system uses."""

from __future__ import annotations

import json

import pytest

from vinu_agent.broker.kill_switch import AuditLogger


@pytest.fixture
def log_path(tmp_path, monkeypatch):
    path = tmp_path / "trade_audit.log"
    monkeypatch.setattr(AuditLogger, "LOG_PATH", path)
    return path


def _last(path) -> dict:
    return json.loads(path.read_text(encoding="utf-8").strip().splitlines()[-1])


def test_a_paper_stack_writes_paper_entries(log_path, monkeypatch):
    monkeypatch.setenv("VINU_ACCOUNT_MODE", "paper")
    AuditLogger.log(AuditLogger.ORDER_REJECTED, {"reason": "x"}, symbol="AAPL")
    entry = _last(log_path)
    assert entry["account_mode"] == "paper" and entry["paper_trading"] is True


def test_a_real_stack_writes_real_entries(log_path, monkeypatch):
    monkeypatch.setenv("VINU_ACCOUNT_MODE", "real")
    monkeypatch.setenv("VINU_REAL_CAPITAL", "20")
    AuditLogger.log(AuditLogger.ORDER_PLACED, {"qty": 1}, symbol="AAPL")
    entry = _last(log_path)
    assert entry["account_mode"] == "real" and entry["paper_trading"] is False


def test_an_explicit_flag_from_the_caller_is_kept(log_path, monkeypatch):
    monkeypatch.setenv("VINU_ACCOUNT_MODE", "paper")
    AuditLogger.log(AuditLogger.ORDER_PLACED, {}, symbol="AAPL", paper_trading=False)
    assert _last(log_path)["paper_trading"] is False


def test_an_unreadable_setting_does_not_stop_the_write(log_path, monkeypatch):
    monkeypatch.setenv("VINU_ACCOUNT_MODE", "nonsense")
    AuditLogger.log(AuditLogger.ORDER_PLACED, {}, symbol="AAPL")
    assert _last(log_path)["account_mode"] == "unknown"
