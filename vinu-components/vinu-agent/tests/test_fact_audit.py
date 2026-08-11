"""Tests for FactAuditor -- the numeric-claim-grounding guardrail wired
into every AgentLoop (agent/loop.py). Covers the pre-existing direct-tool
behavior and the nested-specialist-content fix: a manager's only "tool
result" for a delegated task is delegate_to_agent's JSON, whose real
numbers live inside the specialist's prose `content` string, not as raw
JSON numeric literals -- confirmed as a real false-positive source by two
separate real-LLM test runs against risk_gatekeeper/capital_allocator/
research, see New-talk-agents/implementation/00-status.md.
"""

from __future__ import annotations

import json

from vinu_agent.audit.fact_audit import FactAuditor


def _tool_msg(name: str, content: str) -> dict:
    return {"role": "tool", "name": name, "tool_call_id": "call_1", "content": content}


class TestDirectToolGrounding:
    """Pre-existing behavior: numbers as raw JSON numeric literals in this
    turn's own tool results."""

    def test_price_verified_from_this_turns_tool_result(self) -> None:
        history = [_tool_msg("get_portfolio", json.dumps({"account": {"portfolio_value": 100000.0}}))]
        findings = FactAuditor().audit("Portfolio value: $100,000", history)
        assert findings[0]["verdict"] == "Verified"

    def test_price_fails_when_not_grounded_anywhere(self) -> None:
        history = [_tool_msg("get_portfolio", json.dumps({"account": {"portfolio_value": 100000.0}}))]
        findings = FactAuditor().audit("Portfolio value: $999,999", history)
        assert findings[0]["verdict"] == "Fail"

    def test_stale_when_only_in_historical_context(self) -> None:
        historical = {"role": "tool", "content": json.dumps({"price": 50.0})}
        findings = FactAuditor().audit("Price: $50", [historical])
        assert findings[0]["verdict"] == "Stale"

    def test_no_claims_returns_no_findings(self) -> None:
        assert FactAuditor().audit("Everything looks fine, no numbers here.", []) == []


class TestNestedSpecialistContentGrounding:
    """The fix: numbers embedded in a specialist's prose, wrapped inside
    delegate_to_agent's JSON `content` field, must now be found too."""

    def test_price_verified_inside_nested_specialist_prose(self) -> None:
        history = [_tool_msg("delegate_to_agent", json.dumps({
            "status": "completed",
            "agent": "allocation_analyst",
            "content": "Funded: $34,000 for art_abc123, reason: deflated_sharpe=1.4",
        }))]
        findings = FactAuditor().audit("Amount: $34,000", history)
        assert findings[0]["verdict"] == "Verified"

    def test_pct_verified_inside_nested_specialist_prose(self) -> None:
        """Reproduces the exact real-LLM run finding: risk_gatekeeper's
        manager reported "20%" (a real concentration limit computed by
        exposure_reviewer) and it read as ungrounded before this fix."""
        history = [_tool_msg("delegate_to_agent", json.dumps({
            "status": "completed",
            "agent": "exposure_reviewer",
            "content": "The account has $100,000 in portfolio value, so a new AAPL "
                        "position would not exceed the 20% concentration limit (max $20,000).",
        }))]
        findings = FactAuditor().audit(
            "The verdict: APPROVED. Concentration limit: 20% (max $20,000).", history,
        )
        by_type = {f["claim_type"]: f["verdict"] for f in findings}
        assert by_type["pct"] == "Verified"
        assert by_type["price"] == "Verified"

    def test_backtest_metrics_verified_inside_nested_specialist_prose(self) -> None:
        """Reproduces the research-team real-LLM run: backtest_runner's
        reported Sharpe/max-drawdown numbers, repeated by the manager,
        used to read as 5 separate Fails."""
        history = [_tool_msg("delegate_to_agent", json.dumps({
            "status": "completed",
            "agent": "backtest_runner",
            "content": "Sharpe ratio: -0.03373194414392755\nMax drawdown: -27.97%\n"
                       "Win rate: 40.4%\nTotal return: -6.47%\nTrade count: 62",
        }))]
        findings = FactAuditor().audit(
            "Max drawdown: -27.97%. Win rate: 40.4%. Total return: -6.47%.", history,
        )
        assert all(f["verdict"] == "Verified" for f in findings)

    def test_genuinely_ungrounded_number_still_fails(self) -> None:
        """The fix must not turn the auditor into a rubber stamp -- a
        number nowhere in any tool result, nested or not, is still a Fail."""
        history = [_tool_msg("delegate_to_agent", json.dumps({
            "status": "completed",
            "agent": "allocation_analyst",
            "content": "Funded: $34,000 for art_abc123.",
        }))]
        findings = FactAuditor().audit("Amount: $999,000", history)
        assert findings[0]["verdict"] == "Fail"

    def test_booleans_are_not_treated_as_numeric_claims(self) -> None:
        """bool is a subclass of int in Python -- a JSON `"success": true`
        field must not silently count as a match for a claimed value of 1."""
        history = [_tool_msg("delegate_to_agent", json.dumps({"status": "completed", "success": True}))]
        findings = FactAuditor().audit("Total return: 1%", history)
        assert findings[0]["verdict"] == "Fail"
