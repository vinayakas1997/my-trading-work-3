"""Scenario 01 — clear uptrend signal (llm-scenarios-test).

Acceptance test for the real LLM agent loop (`vinu_agent/agent/loop.py`):
everything in `vinu-live/tests/test_pre_live_scenarios.py` deliberately
bypassed the LLM; this closes that layer. Follows the repo's own test
convention (`vinu-agent/tests/test_loop.py` FakeLLM +
`test_agent_integration.py` ScriptedLLM): a scripted stand-in plays the
role of the LLM, and we assert BEHAVIOR (right tool, right order,
mandate caps, no fabricated prices) — never exact wording.

Run from anywhere:
    python test_scenario.py
or
    pytest test_scenario.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Make `_scenario_helpers` (and via it, `vinu_agent`) importable when run
# straight from this folder.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _scenario_helpers import (  # noqa: E402
    MAX_ORDER_VALUE,
    MAX_POSITION_VALUE,
    BaseTool,
    ScriptedLLM,
    ToolRegistry,
    AgentLoop,
    _assert_no_ungrounded_claims,
    _call,
    _tool_history,
)

UPTREND_CANDLES = [
    {"date": "2026-08-28", "close": 104.10, "volume": 41_000_000},
    {"date": "2026-08-29", "close": 106.25, "volume": 44_500_000},
    {"date": "2026-09-01", "close": 108.40, "volume": 47_000_000},
    {"date": "2026-09-02", "close": 110.15, "volume": 52_300_000},
    {"date": "2026-09-03", "close": 112.40, "volume": 58_100_000},
]
OBSERVED_CLOSE = UPTREND_CANDLES[-1]["close"]  # 112.40 — the only price the agent may cite


class StubStockPriceTool(BaseTool):
    """Stand-in for the real `get_stock_price` (readonly data tool)."""

    name = "get_stock_price"
    description = "Get daily candles for a symbol"
    parameters = {"symbol": {"type": "string", "description": "Ticker"}}
    is_readonly = True

    def __init__(self, candles: Optional[List[Dict]] = None):
        self.calls: List[Dict] = []
        self._candles = UPTREND_CANDLES if candles is None else candles

    def execute(self, **kwargs: Any) -> str:
        self.calls.append(kwargs)
        if not self._candles:
            return json.dumps({"status": "error", "message": "no data for symbol"})
        return json.dumps({"symbol": kwargs.get("symbol"), "candles": self._candles})


class StubSubmitOrderTool(BaseTool):
    """Stand-in for the real `submit_order`, with the real guard semantics:
    fail-closed on unknown price, reject over the mandate caps."""

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
        # Echo the order back like the real trade_tool does (proposal /
        # order_placed carry symbol/side/qty) so the post-hoc FactAuditor
        # can verify shares claims against this payload.
        base = {"symbol": kwargs.get("symbol"), "side": kwargs.get("side"), "qty": qty, "limit_price": price}
        if price <= 0:
            outcome = {"status": "rejected", "reason": "ORDER_VALUE_UNKNOWN"} | base
            self.calls[-1]["_outcome"] = outcome
            return json.dumps(outcome)
        value = qty * price
        if value > MAX_ORDER_VALUE or value > MAX_POSITION_VALUE:
            outcome = {"status": "rejected", "reason": "exceeds mandate cap", "value": value} | base
            self.calls[-1]["_outcome"] = outcome
            return json.dumps(outcome)
        outcome = {"status": "submitted", "value": value} | base
        self.calls[-1]["_outcome"] = outcome
        return json.dumps(outcome)


def test_uptrend_buys_within_mandate_and_cites_observed_price() -> None:
    price_tool = StubStockPriceTool()
    order_tool = StubSubmitOrderTool()
    registry = ToolRegistry()
    registry.register(price_tool)
    registry.register(order_tool)

    llm = ScriptedLLM(
        [
            {"content": "", "tool_calls": [_call("c1", "get_stock_price", {"symbol": "AAPL"})]},
            {
                "content": "",
                "tool_calls": [
                    _call(
                        "c2",
                        "submit_order",
                        {"symbol": "AAPL", "qty": 10, "side": "buy", "limit_price": OBSERVED_CLOSE},
                    )
                ],
            },
            {"content": f"AAPL uptrend confirmed, closed at {OBSERVED_CLOSE}. Submitted buy 10 shares."},
        ]
    )
    result = AgentLoop(registry=registry, llm=llm, max_iterations=10).run(
        [{"role": "user", "content": Path(__file__).with_name("prompt.md").read_text()}]
    )

    assert result["status"] == "completed"
    # 1. data before order — never trade on memory
    tool_names = [m.get("name") for m in _tool_history(result)]
    assert tool_names == ["get_stock_price", "submit_order"]
    assert len(order_tool.calls) == 1, "at most one order per expected.md #2"
    # 2. mandate caps respected
    order_args = {k: v for k, v in order_tool.calls[0].items() if not k.startswith("_")}
    assert order_args["side"] == "buy"
    value = order_args["qty"] * order_args["limit_price"]
    assert value <= MAX_ORDER_VALUE and value <= MAX_POSITION_VALUE
    assert order_tool.calls[0]["_outcome"]["status"] == "submitted"
    # 3. grounding — cited price came from a tool payload, not invented
    price_payload = next(m for m in _tool_history(result) if m.get("name") == "get_stock_price")["content"]
    assert str(OBSERVED_CLOSE) in price_payload
    assert str(OBSERVED_CLOSE) in result["content"]
    _assert_no_ungrounded_claims(result)


def test_oversized_order_is_rejected_by_mandate() -> None:
    price_tool = StubStockPriceTool()
    order_tool = StubSubmitOrderTool()
    registry = ToolRegistry()
    registry.register(price_tool)
    registry.register(order_tool)

    llm = ScriptedLLM(
        [
            {"content": "", "tool_calls": [_call("c1", "get_stock_price", {"symbol": "AAPL"})]},
            {
                "content": "",
                "tool_calls": [
                    _call(
                        "c2",
                        "submit_order",
                        {"symbol": "AAPL", "qty": 10_000, "side": "buy", "limit_price": OBSERVED_CLOSE},
                    )
                ],
            },
            {"content": "Order too big, rejected."},
        ]
    )
    result = AgentLoop(registry=registry, llm=llm, max_iterations=10).run(
        [{"role": "user", "content": "Buy AAPL uptrend."}]
    )

    assert result["status"] == "completed"
    assert order_tool.calls[0]["_outcome"]["status"] == "rejected"
    _assert_no_ungrounded_claims(result)


def test_missing_data_means_no_order() -> None:
    price_tool = StubStockPriceTool(candles=[])
    order_tool = StubSubmitOrderTool()
    registry = ToolRegistry()
    registry.register(price_tool)
    registry.register(order_tool)

    llm = ScriptedLLM(
        [
            {"content": "", "tool_calls": [_call("c1", "get_stock_price", {"symbol": "AAPL"})]},
            {"content": "No usable price data for AAPL, cannot proceed without it."},
        ]
    )
    result = AgentLoop(registry=registry, llm=llm, max_iterations=10).run(
        [{"role": "user", "content": "Buy AAPL uptrend."}]
    )

    assert result["status"] == "completed"
    assert order_tool.calls == [], "must not trade without data"
    assert "cannot proceed" in result["content"].lower()
    _assert_no_ungrounded_claims(result)


if __name__ == "__main__":
    test_uptrend_buys_within_mandate_and_cites_observed_price()
    print("PASS test_uptrend_buys_within_mandate_and_cites_observed_price")
    test_oversized_order_is_rejected_by_mandate()
    print("PASS test_oversized_order_is_rejected_by_mandate")
    test_missing_data_means_no_order()
    print("PASS test_missing_data_means_no_order")
