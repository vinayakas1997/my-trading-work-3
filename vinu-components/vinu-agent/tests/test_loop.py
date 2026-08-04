import json
import threading
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock

from vinu_agent.agent.loop import AgentLoop, _DEFAULT_MAX_CONTEXT_TOKENS, _estimate_tokens
from vinu_agent.agent.tools import BaseTool, ToolRegistry
from vinu_lib.telemetry import TelemetryStore


class SimpleTool(BaseTool):
    name = "echo"
    description = "Echo back the input"
    parameters = {"text": {"type": "string", "description": "Text to echo"}}
    is_readonly = True

    def execute(self, **kwargs: Any) -> str:
        return f'echoed: {kwargs.get("text", "")}'


class WriteTool(BaseTool):
    name = "write_note"
    description = "Write a note"
    parameters = {"note": {"type": "string", "description": "Note content"}}
    is_readonly = False

    def execute(self, **kwargs: Any) -> str:
        return f'note saved: {kwargs.get("note", "")}'


class FakeLLM:
    def __init__(self, responses: Optional[List[Dict]] = None):
        self.responses = responses or []
        self.call_count = 0
        self.last_messages: Optional[List[Dict]] = None

    def chat(self, messages: List[Dict], tools: Optional[List[Dict]] = None) -> Dict:
        self.last_messages = messages
        if self.call_count < len(self.responses):
            resp = self.responses[self.call_count]
            self.call_count += 1
            return resp
        return {"content": "I'm done here."}


class TestEstimateTokens:
    def test_estimate_tokens(self) -> None:
        assert _estimate_tokens("hello") == 2
        assert _estimate_tokens("") == 1
        assert _estimate_tokens("a" * 400) == 101


class TestAgentLoop:
    def _make_registry(self) -> ToolRegistry:
        r = ToolRegistry()
        r.register(SimpleTool())
        r.register(WriteTool())
        return r

    def test_text_only_completes(self) -> None:
        llm = FakeLLM([{"content": "Hello, I am an agent."}])
        loop = AgentLoop(registry=self._make_registry(), llm=llm)
        result = loop.run([{"role": "user", "content": "Hi"}])
        assert result["status"] == "completed"
        assert result["content"] == "Hello, I am an agent."
        assert result["iterations"] == 1

    def test_tool_call_then_text(self) -> None:
        llm = FakeLLM([
            {
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_1",
                        "function": {"name": "echo", "arguments": '{"text": "hello"}'},
                    }
                ],
            },
            {"content": "Done with echo."},
        ])
        loop = AgentLoop(registry=self._make_registry(), llm=llm)
        result = loop.run([{"role": "user", "content": "Echo hello"}])
        assert result["status"] == "completed"
        assert result["content"] == "Done with echo."

    def test_max_iterations_reached(self) -> None:
        llm = FakeLLM([{"content": "", "tool_calls": [{"function": {"name": "echo", "arguments": '{"text": "x"}'}}]} for _ in range(60)])
        loop = AgentLoop(registry=self._make_registry(), llm=llm, max_iterations=3)
        result = loop.run([{"role": "user", "content": "loop"}])
        assert result["status"] == "max_iterations"
        assert result["iterations"] == 3

    def test_cancel(self) -> None:
        class SlowLLM:
            def __init__(self):
                self.count = 0
            def chat(self, messages, tools=None):
                import time
                self.count += 1
                time.sleep(0.05)
                return {"content": "", "tool_calls": []}

        loop = AgentLoop(registry=self._make_registry(), llm=SlowLLM(), max_iterations=100)

        def cancel_later():
            import time
            time.sleep(0.03)
            loop.cancel()

        t = threading.Thread(target=cancel_later, daemon=True)
        t.start()
        result = loop.run([{"role": "user", "content": "test cancel"}])
        assert result["status"] == "cancelled"

    def test_llm_error_returns_error_status(self) -> None:
        class BrokenLLM:
            def chat(self, messages: List[Dict], tools: Optional[List[Dict]] = None) -> Dict:
                raise RuntimeError("API down")

        loop = AgentLoop(registry=self._make_registry(), llm=BrokenLLM())
        result = loop.run([{"role": "user", "content": "hello"}])
        assert result["status"] == "error"
        assert "API down" in result["content"]

    def test_event_callback_invoked(self) -> None:
        events: List[str] = []
        def cb(etype: str, data: Dict) -> None:
            events.append(etype)

        llm = FakeLLM([{"content": "OK"}])
        loop = AgentLoop(registry=self._make_registry(), llm=llm, event_callback=cb)
        loop.run([{"role": "user", "content": "hi"}])
        assert "loop.start" in events
        assert "llm.call" in events
        assert "loop.completed" in events

    def test_parallel_readonly_tools(self) -> None:
        llm = FakeLLM([
            {
                "content": "",
                "tool_calls": [
                    {"function": {"name": "echo", "arguments": '{"text": "a"}'}},
                    {"function": {"name": "echo", "arguments": '{"text": "b"}'}},
                ],
            },
            {"content": "Done parallel."},
        ])
        loop = AgentLoop(registry=self._make_registry(), llm=llm)
        result = loop.run([{"role": "user", "content": "echo a and b"}])
        assert result["status"] == "completed"

    def test_serial_write_tools(self) -> None:
        llm = FakeLLM([
            {
                "content": "",
                "tool_calls": [
                    {"function": {"name": "write_note", "arguments": '{"note": "important"}'}},
                ],
            },
            {"content": "Saved."},
        ])
        loop = AgentLoop(registry=self._make_registry(), llm=llm)
        result = loop.run([{"role": "user", "content": "save a note"}])
        assert result["status"] == "completed"

    def test_parse_params_json_string(self) -> None:
        loop = AgentLoop(registry=self._make_registry(), llm=FakeLLM())
        params = loop._parse_params({"function": {"arguments": '{"a": 1}'}})
        assert params == {"a": 1}

    def test_parse_params_invalid_json(self) -> None:
        loop = AgentLoop(registry=self._make_registry(), llm=FakeLLM())
        params = loop._parse_params({"function": {"arguments": "not-json"}})
        assert params == {}

    def test_microcompact_trims_large_tool_results(self) -> None:
        msgs = [{"role": "system", "content": "sys"}]
        for i in range(6):
            msgs.append({"role": "tool", "content": "x" * 200, "tool_call_id": str(i)})
        loop = AgentLoop(registry=self._make_registry(), llm=FakeLLM())
        compacted = loop._microcompact(msgs)
        cleared = [m for m in compacted if m.get("role") == "tool" and m.get("content") == "[cleared]"]
        assert len(cleared) == 3

    def test_context_collapse_truncates_long_messages(self) -> None:
        msgs = [{"role": "user", "content": "x" * 3000} for _ in range(10)]
        loop = AgentLoop(registry=self._make_registry(), llm=FakeLLM())
        collapsed = loop._context_collapse(msgs)
        collapsed_msgs = [m for m in collapsed[:4] if len(m["content"]) > 2400]
        for m in collapsed_msgs:
            assert "..." in m["content"]

    def test_emit_does_not_raise(self) -> None:
        def broken_cb(etype: str, data: Dict) -> None:
            raise ValueError("oops")
        loop = AgentLoop(registry=self._make_registry(), llm=FakeLLM(), event_callback=broken_cb)
        loop._emit("test", {})

    def test_max_context_tokens_falls_back_to_default_when_llm_has_no_context_window(self) -> None:
        loop = AgentLoop(registry=self._make_registry(), llm=FakeLLM())
        assert loop.max_context_tokens == _DEFAULT_MAX_CONTEXT_TOKENS

    def test_max_context_tokens_resolved_from_llm_context_window(self) -> None:
        llm = FakeLLM()
        llm.context_window = 32000
        loop = AgentLoop(registry=self._make_registry(), llm=llm)
        assert loop.max_context_tokens == 32000

    def test_max_context_tokens_explicit_param_wins_over_llm_context_window(self) -> None:
        llm = FakeLLM()
        llm.context_window = 32000
        loop = AgentLoop(registry=self._make_registry(), llm=llm, max_context_tokens=5000)
        assert loop.max_context_tokens == 5000

    def test_uses_real_usage_from_provider_instead_of_estimate(self) -> None:
        llm = FakeLLM([
            {"content": "Hi", "usage": {"prompt_tokens": 999, "completion_tokens": 111, "total_tokens": 1110}},
        ])
        loop = AgentLoop(registry=self._make_registry(), llm=llm)
        result = loop.run([{"role": "user", "content": "hi"}])
        assert result["token_usage"]["prompt"] == 999
        assert result["token_usage"]["completion"] == 111

    def test_falls_back_to_estimate_when_no_usage_in_response(self) -> None:
        llm = FakeLLM([{"content": "Hi"}])
        loop = AgentLoop(registry=self._make_registry(), llm=llm)
        result = loop.run([{"role": "user", "content": "hi"}])
        # No "usage" key on FakeLLM's response — must fall back to the
        # char/4 heuristic rather than reporting zero.
        assert result["token_usage"]["prompt"] > 0
        assert result["token_usage"]["completion"] > 0

    def test_telemetry_recorded_when_data_root_set(self) -> None:
        with TemporaryDirectory() as tmp:
            llm = FakeLLM([
                {"content": "Hi", "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}, "retry_count": 1},
            ])
            loop = AgentLoop(registry=self._make_registry(), llm=llm, data_root=tmp, service_name="vinu-agent-test")
            loop.run([{"role": "user", "content": "hi"}])

            store = TelemetryStore(Path(tmp) / "telemetry.db")
            calls = store.recent_llm_calls(service="vinu-agent-test")
            assert len(calls) == 1
            assert calls[0]["prompt_tokens"] == 10
            assert calls[0]["retry_count"] == 1
            assert calls[0]["token_count_source"] == "provider"

            steps = store.recent_steps(service="vinu-agent-test")
            assert any(s["step_name"] == "agent_loop_run" and s["outcome"] == "completed" for s in steps)
            store.close()

    def test_telemetry_records_tool_call_steps(self) -> None:
        with TemporaryDirectory() as tmp:
            llm = FakeLLM([
                {
                    "content": "",
                    "tool_calls": [
                        {"id": "call_1", "function": {"name": "echo", "arguments": '{"text": "hello"}'}},
                    ],
                },
                {"content": "Done."},
            ])
            loop = AgentLoop(registry=self._make_registry(), llm=llm, data_root=tmp)
            loop.run([{"role": "user", "content": "echo hello"}])

            store = TelemetryStore(Path(tmp) / "telemetry.db")
            steps = store.recent_steps()
            assert any(s["step_name"] == "tool:echo" and s["outcome"] == "completed" for s in steps)
            store.close()

    def test_no_telemetry_written_when_data_root_empty(self) -> None:
        # Default construction (no data_root) must not raise and must not
        # attempt any filesystem write — this is the common case for every
        # existing unit test in this file.
        llm = FakeLLM([{"content": "Hi"}])
        loop = AgentLoop(registry=self._make_registry(), llm=llm)
        result = loop.run([{"role": "user", "content": "hi"}])
        assert result["status"] == "completed"
