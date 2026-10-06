"""The loop compacted a COPY of its history on every turn and kept the full one, so after the history first crossed the
threshold every later turn paid for a fresh summarise call plus a merge call (63% of one research run's model time went
on re-summarising the same old messages). A compaction now sticks: later turns build on it."""
import json
from typing import Any, Dict, List, Optional

from vinu_agent.agent.loop import AgentLoop
from vinu_agent.agent.tools import BaseTool, ToolRegistry


class _Big(BaseTool):
    name = "big"
    description = "returns a large result"
    parameters = {}
    is_readonly = True

    def execute(self, **kwargs: Any) -> str:
        return "x" * 2000          # ~1,000 estimated tokens at 2 chars/token


class _CountingLLM:
    def __init__(self, steps: int):
        self.steps, self.step = steps, 0
        self.summaries = 0
        self.merges = 0
        self.max_sent_chars = 0

    def chat(self, messages: List[Dict], tools: Optional[List[Dict]] = None) -> Dict:
        first = messages[0].get("content") or ""
        if first.startswith("Summarize the following"):
            self.summaries += 1
            return {"content": "summary of earlier work"}
        if first.startswith("Merge a previous summary"):
            self.merges += 1
            return {"content": "merged summary"}
        self.max_sent_chars = max(self.max_sent_chars, sum(len(str(m.get("content") or "")) for m in messages))
        self.step += 1
        if self.step <= self.steps:
            return {"content": "", "tool_calls": [{"id": f"c{self.step}", "function": {"name": "big", "arguments": "{}"}}]}
        return {"content": "done"}


def _run(steps: int, window: int):
    registry = ToolRegistry()
    registry.register(_Big())
    llm = _CountingLLM(steps)
    loop = AgentLoop(registry=registry, llm=llm, max_iterations=steps + 5, max_context_tokens=window)
    result = loop.run([{"role": "system", "content": "s"}, {"role": "user", "content": "go"}])
    return llm, result


def test_a_compaction_is_not_redone_every_turn():
    steps = 14
    llm, result = _run(steps, window=3000)
    assert result["status"] == "completed" and llm.summaries >= 1       # compaction really happens...
    assert llm.summaries <= steps // 2                                 # ...but not on every turn (it was ~one per turn)


def test_the_model_is_never_sent_more_than_the_window_allows():
    llm, _ = _run(14, window=3000)
    assert llm.max_sent_chars < 3000 * 2 + 4000        # window in tokens at 2 chars/token, plus the fresh results


def test_the_run_still_ends_with_the_models_own_final_answer():
    _, result = _run(6, window=3000)
    assert result["content"] == "done"
    assert result["history"][-1]["role"] == "assistant" and result["history"][-1]["content"] == "done"
    assert any(m.get("role") == "tool" for m in result["history"])        # the recent tool results are still there
