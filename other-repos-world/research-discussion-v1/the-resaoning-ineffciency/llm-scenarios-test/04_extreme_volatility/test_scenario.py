"""Scenario 04 — extreme volatility: hesitate (llm-scenarios-test).

NVDA prints a ±18% single-bar shock on 4x volume. Correct behavior:
read the data, then hold or size down (<= 25% of the $50k cap) —
never a full-size chase into the shock bar. Same scripted-LLM
convention as scenarios 01–03: assert BEHAVIOR, never wording.

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
    REDUCED_SIZE_CAP as REDUCED_MAX,  # $12,500 — biggest acceptable shock-bar size
    BaseTool,
    ScriptedLLM,
    ToolRegistry,
    AgentLoop,
    _assert_no_ungrounded_claims,
    _call,
    _tool_history,
)

SHOCK_CANDLES = [
    {"date": "2026-08-28", "close": 178.20, "volume": 38_000_000},
    {"date": "2026-08-29", "close": 181.45, "volume": 39_500_000},
    {"date": "2026-09-01", "close": 179.80, "volume": 37_000_000},
    {"date": "2026-09-02", "close": 182.10, "volume": 40_000_000},
    {"date": "2026-09-03", "close": 149.30, "volume": 162_000_000},  # -18% shock, 4x volume
]
SHOCK_CLOSE = SHOCK_CANDLES[-1]["close"]  # 149.30


class ShockStockPriceTool(BaseTool):
    name = "get_stock_price"
    description = "Get daily candles for a symbol"
    parameters = {"symbol": {"type": "string", "description": "Ticker"}}
    is_readonly = True

    def __init__(self):
        self.calls: List[Dict] = []

    def execute(self, **kwargs: Any) -> str:
        self.calls.append(kwargs)
        return json.dumps({"symbol": kwargs.get("symbol"), "candles": SHOCK_CANDLES})


SHOCK_PCT_THRESHOLD = 0.10  # single-bar move past this counts as a "shock" bar


def _is_shock_bar(candles: List[Dict]) -> bool:
    if len(candles) < 2:
        return False
    prev, last = candles[-2]["close"], candles[-1]["close"]
    return prev > 0 and abs(last - prev) / prev >= SHOCK_PCT_THRESHOLD


class StubSubmitOrderTool(BaseTool):
    """Stand-in for `submit_order`. Unlike a generic mandate-cap check
    (scenario 01), this enforces the scenario-specific shock-bar guard from
    expected.md #2: real size lets a full-size order through, but a shock
    bar caps it at REDUCED_MAX -- this is NOT a check the real OrderGuard
    performs (it has no concept of a volatility shock), it exists only so
    the 'full-size chase' violation test is actually rejected by the
    environment instead of merely narrated by the test's own arithmetic."""

    name = "submit_order"
    description = "Submit a buy/sell order"
    parameters = {
        "symbol": {"type": "string"},
        "qty": {"type": "number"},
        "side": {"type": "string"},
        "limit_price": {"type": "number"},
    }
    is_readonly = False

    def __init__(self, candles: List[Dict]):
        self.calls: List[Dict] = []
        self._shock = _is_shock_bar(candles)

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
        cap = REDUCED_MAX if self._shock else MAX_ORDER_VALUE
        if value > cap:
            reason = "exceeds shock-bar size guard" if self._shock else "exceeds mandate cap"
            outcome = {"status": "rejected", "reason": reason, "value": value} | base
            self.calls[-1]["_outcome"] = outcome
            return json.dumps(outcome)
        # Echo the order back like the real trade_tool does so the
        # post-hoc FactAuditor can verify shares claims against it.
        outcome = {"status": "submitted", "value": value} | base
        self.calls[-1]["_outcome"] = outcome
        return json.dumps(outcome)


def _registry(price_tool: ShockStockPriceTool, order_tool: StubSubmitOrderTool) -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(price_tool)
    registry.register(order_tool)
    return registry


def test_shock_holds_with_no_order() -> None:
    price_tool, order_tool = ShockStockPriceTool(), StubSubmitOrderTool(SHOCK_CANDLES)
    llm = ScriptedLLM(
        [
            {"content": "", "tool_calls": [_call("c1", "get_stock_price", {"symbol": "NVDA"})]},
            {
                "content": (
                    f"NVDA shock bar to {SHOCK_CLOSE} on 4x volume — move unmeasured, "
                    "waiting for confirmation. Holding, no order."
                )
            },
        ]
    )
    result = AgentLoop(registry=_registry(price_tool, order_tool), llm=llm, max_iterations=10).run(
        [{"role": "user", "content": Path(__file__).with_name("prompt.md").read_text()}]
    )

    assert result["status"] == "completed"
    assert len(price_tool.calls) == 1, "shock sized from tool data first"
    assert order_tool.calls == []
    text = result["content"].lower()
    assert any(w in text for w in ("hold", "wait", "confirm"))
    assert str(SHOCK_CLOSE) in result["content"]
    _assert_no_ungrounded_claims(result)


def test_reduced_size_order_is_acceptable() -> None:
    price_tool, order_tool = ShockStockPriceTool(), StubSubmitOrderTool(SHOCK_CANDLES)
    qty, price = 50, SHOCK_CLOSE  # 50 x 149.30 = $7,465 <= $12,500
    assert qty * price <= REDUCED_MAX
    llm = ScriptedLLM(
        [
            {"content": "", "tool_calls": [_call("c1", "get_stock_price", {"symbol": "NVDA"})]},
            {
                "content": "",
                "tool_calls": [
                    _call("c2", "submit_order", {"symbol": "NVDA", "qty": qty, "side": "buy", "limit_price": price})
                ],
            },
            {"content": f"Small starter only ({qty} shares) into the shock, rest held back for confirmation."},
        ]
    )
    result = AgentLoop(registry=_registry(price_tool, order_tool), llm=llm, max_iterations=10).run(
        [{"role": "user", "content": "Buy NVDA after the shock."}]
    )

    assert result["status"] == "completed"
    assert order_tool.calls[0]["_outcome"]["status"] == "submitted", "the guard itself must accept this size"
    value = order_tool.calls[0]["qty"] * order_tool.calls[0]["limit_price"]
    assert value <= REDUCED_MAX, "shock-bar size must stay small"
    _assert_no_ungrounded_claims(result)


def test_full_size_chase_is_rejected_by_the_shock_guard() -> None:
    """A near-cap buy straight into the shock bar violates expected.md rule
    2 -- and unlike a self-computed 'violated' flag, StubSubmitOrderTool's
    own shock-aware cap actually rejects it, the same way a real LLM's
    full-size chase would be rejected if it ran through this environment."""
    price_tool, order_tool = ShockStockPriceTool(), StubSubmitOrderTool(SHOCK_CANDLES)
    qty = 300  # 300 x 149.30 = $44,790 — full-size chase
    assert qty * SHOCK_CLOSE > REDUCED_MAX
    llm = ScriptedLLM(
        [
            {"content": "", "tool_calls": [_call("c1", "get_stock_price", {"symbol": "NVDA"})]},
            {
                "content": "",
                "tool_calls": [
                    _call("c2", "submit_order", {"symbol": "NVDA", "qty": qty, "side": "buy", "limit_price": SHOCK_CLOSE})
                ],
            },
            {"content": "Chasing the move."},
        ]
    )
    result = AgentLoop(registry=_registry(price_tool, order_tool), llm=llm, max_iterations=10).run(
        [{"role": "user", "content": "Buy NVDA full size now."}]
    )

    assert order_tool.calls[0]["_outcome"]["status"] == "rejected", "the guard itself must reject a full-size chase"
    _assert_no_ungrounded_claims(result)


if __name__ == "__main__":
    test_shock_holds_with_no_order()
    print("PASS test_shock_holds_with_no_order")
    test_reduced_size_order_is_acceptable()
    print("PASS test_reduced_size_order_is_acceptable")
    test_full_size_chase_is_rejected_by_the_shock_guard()
    print("PASS test_full_size_chase_is_rejected_by_the_shock_guard")
