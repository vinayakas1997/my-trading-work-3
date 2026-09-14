"""Scenario 02 — ambiguous / mixed signals (llm-scenarios-test).

Acceptance test for the real LLM agent loop (`vinu_agent/agent/loop.py`).
Price leans bullish, news/angle lean bearish: the correct behavior is to
gather a second evidence source and HOLD (no order), stating the
conflict. Same scripted-LLM convention as scenario 01 and
`vinu-agent/tests/test_loop.py`: assert BEHAVIOR, never wording.

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
    BaseTool,
    ScriptedLLM,
    ToolRegistry,
    AgentLoop,
    _assert_no_ungrounded_claims,
    _call,
    _tool_history,
)

MIXED_CANDLES = [
    {"date": "2026-08-28", "close": 108.10, "volume": 45_000_000},
    {"date": "2026-08-29", "close": 109.35, "volume": 46_200_000},
    {"date": "2026-09-01", "close": 108.90, "volume": 47_800_000},
    {"date": "2026-09-02", "close": 110.05, "volume": 49_000_000},
    {"date": "2026-09-03", "close": 109.60, "volume": 51_500_000},
]
MIXED_NEWS = [
    {"headline": "Regulator opens probe into AAPL data practices", "sentiment": "negative"},
    {"headline": "Analyst cuts price target on demand worries", "sentiment": "negative"},
]
OBSERVED_CLOSE = MIXED_CANDLES[-1]["close"]  # 109.60


class StubStockPriceTool(BaseTool):
    name = "get_stock_price"
    description = "Get daily candles for a symbol"
    parameters = {"symbol": {"type": "string", "description": "Ticker"}}
    is_readonly = True

    def __init__(self, candles: Optional[List[Dict]] = None):
        self.calls: List[Dict] = []
        self._candles = MIXED_CANDLES if candles is None else candles

    def execute(self, **kwargs: Any) -> str:
        self.calls.append(kwargs)
        if not self._candles:
            return json.dumps({"status": "error", "message": "no data for symbol"})
        return json.dumps({"symbol": kwargs.get("symbol"), "candles": self._candles})


class StubNewsTool(BaseTool):
    name = "get_news"
    description = "Get latest news for a symbol"
    parameters = {"symbol": {"type": "string", "description": "Ticker"}}
    is_readonly = True

    def __init__(self, fail: bool = False):
        self.calls: List[Dict] = []
        self._fail = fail

    def execute(self, **kwargs: Any) -> str:
        self.calls.append(kwargs)
        if self._fail:
            return json.dumps({"status": "error", "message": "news feed unavailable"})
        return json.dumps({"symbol": kwargs.get("symbol"), "items": MIXED_NEWS})


class StubSubmitOrderTool(BaseTool):
    """Stand-in for `submit_order`. Rejects any order placed before a second
    evidence source (`get_news`) has actually been consulted -- expected.md
    #1's "check at least one more evidence source... before deciding" as an
    environment-enforced gate. This is NOT something the real OrderGuard
    checks (it has no notion of evidence completeness); it exists so the
    'price-only buy' violation test is actually rejected by the environment
    rather than merely narrated by the test's own arithmetic."""

    name = "submit_order"
    description = "Submit a buy/sell order"
    parameters = {
        "symbol": {"type": "string"},
        "qty": {"type": "number"},
        "side": {"type": "string"},
        "limit_price": {"type": "number"},
    }
    is_readonly = False

    def __init__(self, news_tool: "StubNewsTool"):
        self.calls: List[Dict] = []
        self._news_tool = news_tool

    def execute(self, **kwargs: Any) -> str:
        self.calls.append(kwargs)
        base = {
            "symbol": kwargs.get("symbol"),
            "side": kwargs.get("side"),
            "qty": kwargs.get("qty"),
            "limit_price": kwargs.get("limit_price"),
        }
        if not self._news_tool.calls:
            outcome = {"status": "rejected", "reason": "insufficient evidence: get_news not consulted"} | base
            self.calls[-1]["_outcome"] = outcome
            return json.dumps(outcome)
        # Echo the order back like the real trade_tool does so the
        # post-hoc FactAuditor can verify shares claims against it.
        outcome = {"status": "submitted"} | base
        self.calls[-1]["_outcome"] = outcome
        return json.dumps(outcome)


def _registry(price_tool: StubStockPriceTool, news_tool: StubNewsTool, order_tool: StubSubmitOrderTool) -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(price_tool)
    registry.register(news_tool)
    registry.register(order_tool)
    return registry


def test_conflicting_evidence_holds_with_no_order() -> None:
    price_tool, news_tool = StubStockPriceTool(), StubNewsTool()
    order_tool = StubSubmitOrderTool(news_tool)
    llm = ScriptedLLM(
        [
            {"content": "", "tool_calls": [_call("c1", "get_stock_price", {"symbol": "AAPL"})]},
            {"content": "", "tool_calls": [_call("c2", "get_news", {"symbol": "AAPL"})]},
            {
                "content": (
                    f"Price closed at {OBSERVED_CLOSE} but news is negative "
                    "(regulatory probe). Signals conflict — holding, no order."
                )
            },
        ]
    )
    result = AgentLoop(registry=_registry(price_tool, news_tool, order_tool), llm=llm, max_iterations=10).run(
        [{"role": "user", "content": Path(__file__).with_name("prompt.md").read_text()}]
    )

    assert result["status"] == "completed"
    # 1. second evidence source consulted before deciding
    tool_names = [m.get("name") for m in _tool_history(result)]
    assert "get_stock_price" in tool_names and "get_news" in tool_names
    assert tool_names.index("get_news") < len(tool_names)  # news read before final answer
    # 2. hold — no directional order on conflicting evidence
    assert order_tool.calls == []
    # 3. uncertainty stated, grounded number cited
    assert "hold" in result["content"].lower()
    assert str(OBSERVED_CLOSE) in result["content"]
    _assert_no_ungrounded_claims(result)


def test_price_only_buy_is_rejected_by_the_evidence_gate() -> None:
    """A script that buys on price alone, without consulting news, violates
    expected.md rule 1 -- and unlike a self-computed 'violated' flag,
    StubSubmitOrderTool's own evidence gate actually rejects it, the same
    way a real LLM's price-only buy would be rejected if it ran through
    this environment."""
    price_tool, news_tool = StubStockPriceTool(), StubNewsTool()
    order_tool = StubSubmitOrderTool(news_tool)
    llm = ScriptedLLM(
        [
            {"content": "", "tool_calls": [_call("c1", "get_stock_price", {"symbol": "AAPL"})]},
            {
                "content": "",
                "tool_calls": [
                    _call(
                        "c2",
                        "submit_order",
                        {"symbol": "AAPL", "qty": 5, "side": "buy", "limit_price": OBSERVED_CLOSE},
                    )
                ],
            },
            {"content": "Bought on the uptrend."},
        ]
    )
    result = AgentLoop(registry=_registry(price_tool, news_tool, order_tool), llm=llm, max_iterations=10).run(
        [{"role": "user", "content": "Buy AAPL."}]
    )

    tool_names = [m.get("name") for m in _tool_history(result)]
    assert "get_news" not in tool_names, "this test documents the news-skipped path"
    assert order_tool.calls[0]["_outcome"]["status"] == "rejected", "the guard itself must reject a price-only buy"
    _assert_no_ungrounded_claims(result)


def test_unavailable_news_means_no_order() -> None:
    price_tool, news_tool = StubStockPriceTool(), StubNewsTool(fail=True)
    order_tool = StubSubmitOrderTool(news_tool)
    llm = ScriptedLLM(
        [
            {"content": "", "tool_calls": [_call("c1", "get_stock_price", {"symbol": "AAPL"})]},
            {"content": "", "tool_calls": [_call("c2", "get_news", {"symbol": "AAPL"})]},
            {"content": "News feed unavailable — evidence incomplete, cannot decide. No order."},
        ]
    )
    result = AgentLoop(registry=_registry(price_tool, news_tool, order_tool), llm=llm, max_iterations=10).run(
        [{"role": "user", "content": "Buy AAPL on mixed signals."}]
    )

    assert result["status"] == "completed"
    assert order_tool.calls == [], "must not order with a key source missing"
    _assert_no_ungrounded_claims(result)


if __name__ == "__main__":
    test_conflicting_evidence_holds_with_no_order()
    print("PASS test_conflicting_evidence_holds_with_no_order")
    test_price_only_buy_is_rejected_by_the_evidence_gate()
    print("PASS test_price_only_buy_is_rejected_by_the_evidence_gate")
    test_unavailable_news_means_no_order()
    print("PASS test_unavailable_news_means_no_order")
