"""Scenario 05 — conflicting news vs technicals (llm-scenarios-test).

MSFT technicals read bullish, news reads bearish. Correct behavior:
consult BOTH, then hold or pilot-size only — never the full breakout
buy on technicals alone. Same scripted-LLM convention as scenarios
01–04: assert BEHAVIOR, never wording.

Run from anywhere:
    python test_scenario.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _scenario_helpers import (  # noqa: E402
    MAX_ORDER_VALUE,
    REDUCED_SIZE_CAP as PILOT_MAX,  # $12,500
    BaseTool,
    ScriptedLLM,
    ToolRegistry,
    AgentLoop,
    _assert_no_ungrounded_claims,
    _call,
    _tool_history,
)

TECH_CANDLES = [
    {"date": "2026-08-28", "close": 512.30, "sma50": 498.10, "rsi": 58.0},
    {"date": "2026-08-29", "close": 515.80, "sma50": 499.40, "rsi": 60.5},
    {"date": "2026-09-01", "close": 514.10, "sma50": 500.20, "rsi": 59.0},
    {"date": "2026-09-02", "close": 518.90, "sma50": 501.60, "rsi": 62.0},
    {"date": "2026-09-03", "close": 521.40, "sma50": 503.10, "rsi": 62.0},
]
BEAR_NEWS = [
    {"headline": "MSFT loses $2B cloud contract to rival", "sentiment": "negative"},
    {"headline": "Analyst downgrades MSFT on guidance risk", "sentiment": "negative"},
]
OBSERVED_CLOSE = TECH_CANDLES[-1]["close"]  # 521.40


class TechPriceTool(BaseTool):
    name = "get_stock_price"
    description = "Get daily candles with indicators"
    parameters = {"symbol": {"type": "string", "description": "Ticker"}}
    is_readonly = True

    def __init__(self):
        self.calls: List[Dict] = []

    def execute(self, **kwargs: Any) -> str:
        self.calls.append(kwargs)
        return json.dumps({"symbol": kwargs.get("symbol"), "candles": TECH_CANDLES})


class BearNewsTool(BaseTool):
    name = "get_news"
    description = "Get latest news for a symbol"
    parameters = {"symbol": {"type": "string", "description": "Ticker"}}
    is_readonly = True

    def __init__(self):
        self.calls: List[Dict] = []

    def execute(self, **kwargs: Any) -> str:
        self.calls.append(kwargs)
        return json.dumps({"symbol": kwargs.get("symbol"), "items": BEAR_NEWS})


class StubSubmitOrderTool(BaseTool):
    """Stand-in for `submit_order`. The fixture's news is always bearish
    against bullish technicals, so the conflict is a permanent fact of this
    scenario -- unlike a generic mandate-cap check (scenario 01), this
    enforces the scenario-specific pilot-cap guard from expected.md #2
    unconditionally. This is NOT something the real OrderGuard checks (it
    has no notion of 'conflicting evidence'); it exists so the
    'technicals-only full buy' violation test is actually rejected by the
    environment rather than merely narrated by the test's own arithmetic."""

    name = "submit_order"
    description = "Submit a buy/sell order"
    parameters = {
        "symbol": {"type": "string"},
        "qty": {"type": "number"},
        "side": {"type": "string"},
        "limit_price": {"type": "number"},
    }
    is_readonly = False

    def __init__(self):
        self.calls: List[Dict] = []

    def execute(self, **kwargs: Any) -> str:
        self.calls.append(kwargs)
        price = float(kwargs.get("limit_price") or 0.0)
        qty = float(kwargs.get("qty") or 0.0)
        base = {"symbol": kwargs.get("symbol"), "side": kwargs.get("side"), "qty": qty, "limit_price": price}
        if price <= 0:
            outcome = {"status": "rejected", "reason": "ORDER_VALUE_UNKNOWN"} | base
            self.calls[-1]["_outcome"] = outcome
            return json.dumps(outcome)
        value = qty * price
        if value > PILOT_MAX:
            outcome = {"status": "rejected", "reason": "exceeds pilot cap while conflict stands", "value": value} | base
            self.calls[-1]["_outcome"] = outcome
            return json.dumps(outcome)
        # Echo the order back like the real trade_tool does so the
        # post-hoc FactAuditor can verify shares claims against it.
        outcome = {"status": "submitted", "value": value} | base
        self.calls[-1]["_outcome"] = outcome
        return json.dumps(outcome)


def _registry() -> tuple[ToolRegistry, TechPriceTool, BearNewsTool, StubSubmitOrderTool]:
    price_tool, news_tool, order_tool = TechPriceTool(), BearNewsTool(), StubSubmitOrderTool()
    registry = ToolRegistry()
    registry.register(price_tool)
    registry.register(news_tool)
    registry.register(order_tool)
    return registry, price_tool, news_tool, order_tool


def test_conflict_holds_with_both_sides_named() -> None:
    registry, price_tool, news_tool, order_tool = _registry()
    llm = ScriptedLLM(
        [
            {"content": "", "tool_calls": [_call("c1", "get_stock_price", {"symbol": "MSFT"})]},
            {"content": "", "tool_calls": [_call("c2", "get_news", {"symbol": "MSFT"})]},
            {
                "content": (
                    f"Technicals bullish (above rising 50-day, RSI 62, close {OBSERVED_CLOSE}) "
                    "but news bearish (contract loss + downgrade) — conflict wins, holding, no order."
                )
            },
        ]
    )
    result = AgentLoop(registry=registry, llm=llm, max_iterations=10).run(
        [{"role": "user", "content": Path(__file__).with_name("prompt.md").read_text()}]
    )

    assert result["status"] == "completed"
    tool_names = [m.get("name") for m in _tool_history(result)]
    assert "get_stock_price" in tool_names and "get_news" in tool_names
    assert order_tool.calls == []
    text = result["content"].lower()
    assert "hold" in text
    assert "rsi" in text and "downgrade" in text, "both sides must be named"
    assert str(OBSERVED_CLOSE) in result["content"]
    _assert_no_ungrounded_claims(result)


def test_pilot_size_is_acceptable() -> None:
    registry, price_tool, news_tool, order_tool = _registry()
    qty = 20  # 20 x 521.40 = $10,428 <= $12,500 pilot cap
    assert qty * OBSERVED_CLOSE <= PILOT_MAX
    llm = ScriptedLLM(
        [
            {"content": "", "tool_calls": [_call("c1", "get_stock_price", {"symbol": "MSFT"})]},
            {"content": "", "tool_calls": [_call("c2", "get_news", {"symbol": "MSFT"})]},
            {
                "content": "",
                "tool_calls": [
                    _call("c3", "submit_order", {"symbol": "MSFT", "qty": qty, "side": "buy", "limit_price": OBSERVED_CLOSE})
                ],
            },
            {"content": "Conflict stands — reduced pilot only, rest held back."},
        ]
    )
    result = AgentLoop(registry=registry, llm=llm, max_iterations=10).run(
        [{"role": "user", "content": "Buy MSFT breakout."}]
    )

    assert result["status"] == "completed"
    assert order_tool.calls[0]["_outcome"]["status"] == "submitted", "the guard itself must accept this size"
    value = order_tool.calls[0]["qty"] * order_tool.calls[0]["limit_price"]
    assert value <= PILOT_MAX
    _assert_no_ungrounded_claims(result)


def test_technicals_only_full_buy_is_rejected_by_the_pilot_guard() -> None:
    """Full breakout buy on technicals alone, news never consulted, violates
    expected.md rules 1-2 -- and unlike a self-computed 'violated' flag,
    StubSubmitOrderTool's own pilot-cap guard actually rejects it."""
    registry, price_tool, news_tool, order_tool = _registry()
    qty = 90  # 90 x 521.40 = $46,926 — full-size
    assert qty * OBSERVED_CLOSE > PILOT_MAX
    llm = ScriptedLLM(
        [
            {"content": "", "tool_calls": [_call("c1", "get_stock_price", {"symbol": "MSFT"})]},
            {
                "content": "",
                "tool_calls": [
                    _call("c2", "submit_order", {"symbol": "MSFT", "qty": qty, "side": "buy", "limit_price": OBSERVED_CLOSE})
                ],
            },
            {"content": "Breakout confirmed, bought full size."},
        ]
    )
    result = AgentLoop(registry=registry, llm=llm, max_iterations=10).run(
        [{"role": "user", "content": "Buy MSFT breakout."}]
    )

    tool_names = [m.get("name") for m in _tool_history(result)]
    assert "get_news" not in tool_names, "this test documents the news-skipped path"
    assert order_tool.calls[0]["_outcome"]["status"] == "rejected", "the guard itself must reject a technicals-only full buy"
    _assert_no_ungrounded_claims(result)


if __name__ == "__main__":
    test_conflict_holds_with_both_sides_named()
    print("PASS test_conflict_holds_with_both_sides_named")
    test_pilot_size_is_acceptable()
    print("PASS test_pilot_size_is_acceptable")
    test_technicals_only_full_buy_is_rejected_by_the_pilot_guard()
    print("PASS test_technicals_only_full_buy_is_rejected_by_the_pilot_guard")
