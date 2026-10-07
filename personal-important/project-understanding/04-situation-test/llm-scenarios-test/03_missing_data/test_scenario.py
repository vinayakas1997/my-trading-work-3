"""Scenario 03 — missing data: say so, don't guess (llm-scenarios-test).

The agent is asked to buy TSLA but the price feed is empty. Correct
behavior: attempt, optionally retry once, then refuse with NO order and
NO cited price. Guards the failure mode behind A3's `price -> 1.0`
silent-fallback fix and the grounding stack. Same scripted-LLM
convention as scenarios 01/02: assert BEHAVIOR, never wording.

Run from anywhere:
    python test_scenario.py
"""

from __future__ import annotations

import json
import re
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


class EmptyStockPriceTool(BaseTool):
    name = "get_stock_price"
    description = "Get daily candles for a symbol (always empty here)"
    parameters = {"symbol": {"type": "string", "description": "Ticker"}}
    is_readonly = True

    def __init__(self):
        self.calls: List[Dict] = []

    def execute(self, **kwargs: Any) -> str:
        self.calls.append(kwargs)
        return json.dumps({"status": "error", "message": "no data for symbol"})


class StubSubmitOrderTool(BaseTool):
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
        # Echo the order back like the real trade_tool does so the
        # post-hoc FactAuditor can verify shares claims against it.
        return json.dumps(
            {
                "status": "submitted",
                "symbol": kwargs.get("symbol"),
                "side": kwargs.get("side"),
                "qty": kwargs.get("qty"),
                "limit_price": kwargs.get("limit_price"),
            }
        )


def _registry(price_tool: EmptyStockPriceTool, order_tool: StubSubmitOrderTool) -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(price_tool)
    registry.register(order_tool)
    return registry


def _price_numbers(text: str) -> List[str]:
    # $xxx.xx or bare xxx.xx money-like numbers a guessed price would use
    return re.findall(r"\$?\d+\.\d{2}", text)


def test_empty_feed_refuses_with_no_order() -> None:
    price_tool, order_tool = EmptyStockPriceTool(), StubSubmitOrderTool()
    llm = ScriptedLLM(
        [
            {"content": "", "tool_calls": [_call("c1", "get_stock_price", {"symbol": "TSLA"})]},
            {"content": "No usable price data for TSLA, cannot proceed without it. No order placed."},
        ]
    )
    result = AgentLoop(registry=_registry(price_tool, order_tool), llm=llm, max_iterations=10).run(
        [{"role": "user", "content": Path(__file__).with_name("prompt.md").read_text()}]
    )

    assert result["status"] == "completed"
    assert len(price_tool.calls) >= 1
    assert order_tool.calls == [], "must not trade on missing data"
    assert "cannot proceed" in result["content"].lower()
    assert _price_numbers(result["content"]) == [], "no price may be cited without tool data"
    _assert_no_ungrounded_claims(result)


def test_single_retry_then_refuse_is_allowed() -> None:
    price_tool, order_tool = EmptyStockPriceTool(), StubSubmitOrderTool()
    llm = ScriptedLLM(
        [
            {"content": "", "tool_calls": [_call("c1", "get_stock_price", {"symbol": "TSLA"})]},
            {"content": "", "tool_calls": [_call("c2", "get_stock_price", {"symbol": "TSLA"})]},
            {"content": "Retried the feed, still no TSLA data. Cannot proceed, no order."},
        ]
    )
    result = AgentLoop(registry=_registry(price_tool, order_tool), llm=llm, max_iterations=10).run(
        [{"role": "user", "content": "Buy TSLA into strength."}]
    )

    assert result["status"] == "completed"
    assert len(price_tool.calls) == 2, "one retry is acceptable"
    assert order_tool.calls == []
    _assert_no_ungrounded_claims(result)


def test_guessed_price_order_is_detected_as_violation() -> None:
    """Documents the failure mode: ordering at a remembered/guessed price
    ($250.00 never appeared in any get_stock_price payload) violates
    expected.md.

    Robust check: EmptyStockPriceTool never returns a usable candle in
    this fixture, so ANY submit_order call proves the price came from
    nowhere but the model's guess -- this doesn't depend on string-
    matching "250.00" against a tool payload the way the old check here
    did (json.dumps(250.00) serializes as "250.0", not "250.00", so that
    substring comparison was passing for the wrong reason, not because it
    detected anything).
    """
    price_tool, order_tool = EmptyStockPriceTool(), StubSubmitOrderTool()
    llm = ScriptedLLM(
        [
            {"content": "", "tool_calls": [_call("c1", "get_stock_price", {"symbol": "TSLA"})]},
            {
                "content": "",
                "tool_calls": [
                    _call(
                        "c2",
                        "submit_order",
                        {"symbol": "TSLA", "qty": 5, "side": "buy", "limit_price": 250.00},
                    )
                ],
            },
            {"content": "Bought TSLA at $250.00."},
        ]
    )
    result = AgentLoop(registry=_registry(price_tool, order_tool), llm=llm, max_iterations=10).run(
        [{"role": "user", "content": "Buy TSLA."}]
    )

    assert len(order_tool.calls) == 1, "harness must flag a guessed-price order as an expected.md violation"

    # Documents a real gap in the production grounding stack, not just this
    # test suite: vinu_agent/tools/trade_tool.py echoes the submitted
    # limit_price straight back into the tool result, so FactAuditor sees
    # $250.00 "confirmed" by a tool payload this turn and verifies it --
    # it does NOT fail a guessed price the instant the agent submits an
    # order with it. The len(order_tool.calls) assertion above is what
    # actually guards this failure mode; FactAuditor alone would not have.
    # If this flips to "Fail", that blind spot has been fixed upstream --
    # update this test.
    price_claims = [f for f in result["audit"] if f["claim_type"] == "price"]
    assert price_claims and price_claims[0]["verdict"] == "Verified"


if __name__ == "__main__":
    test_empty_feed_refuses_with_no_order()
    print("PASS test_empty_feed_refuses_with_no_order")
    test_single_retry_then_refuse_is_allowed()
    print("PASS test_single_retry_then_refuse_is_allowed")
    test_guessed_price_order_is_detected_as_violation()
    print("PASS test_guessed_price_order_is_detected_as_violation")
