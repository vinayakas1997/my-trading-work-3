"""Two tool results of 65,707 and 40,836 characters went to a 40,192-token model in one request; the loop's estimate
(characters / 4, tool definitions ignored) said it fit, the server counted 75,217 tokens and rejected it, and the
research team's Idea Generator lost the call 45 times in an hour."""
import json
from unittest.mock import MagicMock

from vinu_agent.agent.loop import AgentLoop, cap_tool_result


def _loop(window: int) -> AgentLoop:
    registry = MagicMock()
    registry.get_definitions.return_value = [{"type": "function", "function": {"name": "t", "description": "x" * 8000}}]
    return AgentLoop(registry=registry, llm=MagicMock(context_window=window))


def test_one_tool_result_may_take_at_most_a_quarter_of_the_window():
    loop = _loop(40192)
    cap = loop._tool_result_cap()
    assert cap == int(40192 * 0.25 * 2.0) and cap < 25_000
    out = cap_tool_result(name="get_indicators", content="1.2345," * 30_000, limit=cap)
    assert len(out) < cap + 400 and "TRUNCATED" in out


def test_a_small_window_still_gets_a_usable_cap():
    assert _loop(1000)._tool_result_cap() == 2000


def test_dense_output_is_judged_over_budget_and_compacted_before_it_is_sent():
    loop = _loop(40192)
    dense = json.dumps([[round(i * 0.37, 4), round(i * 1.91, 4)] for i in range(9000)])      # ~1.6 chars per token
    messages = [
        {"role": "system", "content": "s"},
        {"role": "user", "content": "go"},
        {"role": "tool", "tool_call_id": "1", "name": "a", "content": dense[:65_000]},
        {"role": "tool", "tool_call_id": "2", "name": "b", "content": dense[:40_000]},
    ]
    loop._auto_compact = MagicMock(return_value=[{"role": "system", "content": "s"}, {"role": "user", "content": "go"}])
    out = loop._apply_context_layers(messages)
    loop._auto_compact.assert_called_once()                 # it used to pass the request through untouched
    assert len(json.dumps(out)) < 1000
