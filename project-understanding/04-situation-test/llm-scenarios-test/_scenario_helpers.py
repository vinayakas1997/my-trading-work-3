"""Shared scaffolding for the llm-scenarios-test acceptance tests.

Each 0N_*/test_scenario.py scenario used to copy-paste this same
ScriptedLLM / _call / _tool_history / grounding-check boilerplate --
five near-identical copies that would all need editing by hand if e.g.
the real mandate cap in vinu_agent/broker/mandate.py ever changes. This
is the one place that boilerplate lives now.

Import with the same sys.path trick each scenario already uses:

    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from _scenario_helpers import ScriptedLLM, _call, _tool_history, ...
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

_HERE = Path(__file__).resolve()
_VINU_AGENT_SRC = _HERE.parents[4] / "vinu-components" / "vinu-agent"
if str(_VINU_AGENT_SRC) not in sys.path:
    sys.path.insert(0, str(_VINU_AGENT_SRC))

from vinu_agent.agent.loop import AgentLoop  # noqa: E402,F401
from vinu_agent.agent.tools import BaseTool, ToolRegistry  # noqa: E402,F401

# Mirror of the deployed mandate caps (mandate.py defaults + entrypoint.sh):
# max_order_value=50000, max_position_pct=0.25, test equity=200000.
MAX_ORDER_VALUE = 50_000.0
EQUITY = 200_000.0
MAX_POSITION_VALUE = 0.25 * EQUITY
# 25% of the mandate cap -- the "reduced/pilot" ceiling scenarios 04 and 05
# each enforce when their own scenario-specific guard is on (shock bar /
# standing news-vs-technicals conflict). Not a real OrderGuard field.
REDUCED_SIZE_CAP = 0.25 * MAX_ORDER_VALUE


class ScriptedLLM:
    """Plays a fixed script of LLM turns (see vinu-agent/tests/test_loop.py
    FakeLLM). Stands in for the real LLM so these tests exercise AgentLoop
    and the tool guards deterministically."""

    def __init__(self, responses: List[Dict]):
        self.responses = responses
        self.call_count = 0

    def chat(self, messages: List[Dict], tools: Optional[List[Dict]] = None) -> Dict:
        resp = self.responses[min(self.call_count, len(self.responses) - 1)]
        self.call_count += 1
        return resp


def _call(call_id: str, name: str, arguments: Dict) -> Dict:
    return {"id": call_id, "function": {"name": name, "arguments": json.dumps(arguments)}}


def _tool_history(result: Dict) -> List[Dict]:
    return [m for m in result.get("history", []) if m.get("role") == "tool"]


def _assert_no_ungrounded_claims(result: Dict) -> None:
    """AgentLoop already runs the real FactAuditor on every completed run
    (loop.py's _build_result) and returns its findings as result["audit"].
    A "Fail" verdict means a number in the final answer matched no tool
    result this turn or any prior turn: a genuine hallucination, not just
    "wrong number cited".

    Known blind spot (see 03_missing_data's guessed-price test): trade_tool
    echoes a submitted limit_price straight back into its own tool result,
    so a fabricated price becomes "Verified" the instant it's submitted as
    an order argument. This check still catches everything else -- prices
    from get_stock_price, shares/pct claims not backed by any tool data --
    which is why it's worth asserting everywhere, not just skipped."""
    failed = [f for f in result.get("audit", []) if f["verdict"] == "Fail"]
    assert not failed, f"FactAuditor flagged ungrounded claims: {failed}"
