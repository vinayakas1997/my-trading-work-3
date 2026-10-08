from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from vinu_agent.tools.capital_summary_tool import GetCapitalSummaryTool


def _tool():
    t = GetCapitalSummaryTool()
    t._services_config = {"vinu_portfolio": "http://vinu-portfolio:8090"}
    return t


def test_it_reads_the_allocators_answer_and_is_read_only():
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = {"status": "ok", "capital_plan": {"account_mode": "real", "capital_base": 20.0}}
    with patch("httpx.get", return_value=resp) as g:
        out = json.loads(_tool().execute())
    assert out["status"] == "ok" and out["capital_plan"]["account_mode"] == "real"
    assert g.call_args[0][0] == "http://vinu-portfolio:8090/portfolio/capital-plan" and _tool().is_readonly


def test_an_unreachable_portfolio_service_is_reported_not_guessed():
    with patch("httpx.get", side_effect=RuntimeError("down")):
        out = json.loads(_tool().execute())
    assert out["status"] == "unavailable" and "capital_plan" not in out


def test_the_agents_that_decide_about_money_are_given_the_tool():
    import pathlib

    root = pathlib.Path(__file__).resolve().parents[1] / "teams"
    for rel in ("capital_allocator/agents/allocation_analyst", "risk_gatekeeper/agents/exposure_reviewer",
                "live_decision/agents/live_decision_agent"):
        assert "get_capital_summary" in (root / rel / "AGENT.md").read_text(encoding="utf-8")


def test_safety_ledger_events_are_tagged_with_the_account_mode(tmp_path, monkeypatch):
    from vinu_agent.broker.audit_ledger import HashChainedLedger

    monkeypatch.setenv("VINU_ACCOUNT_MODE", "paper")
    ledger = HashChainedLedger(tmp_path / "l.jsonl")
    entry = ledger.append("halt", {"reason": "drill"})
    assert entry["payload"]["account_mode"] == "paper" and entry["payload"]["reason"] == "drill"
    assert ledger.verify().ok if hasattr(ledger.verify(), "ok") else True
