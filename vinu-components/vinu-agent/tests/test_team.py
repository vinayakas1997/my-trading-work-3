import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from vinu_agent.agent.team import (
    DelegateToAgentTool,
    TeamManager,
    _extract_verdict,
    _tag_event_callback,
    load_agent_spec,
    load_team_spec,
)
from vinu_agent.agent.tools import BaseTool, ToolRegistry


class EchoTool(BaseTool):
    name = "echo"
    description = "Echo back the input"
    parameters = {"text": {"type": "string", "description": "Text to echo"}}
    is_readonly = True

    def execute(self, **kwargs: Any) -> str:
        return f'echoed: {kwargs.get("text", "")}'


class FakeLLM:
    def __init__(self, responses: Optional[List[Dict]] = None):
        self.responses = responses or []
        self.call_count = 0
        self.last_tools: Optional[List[Dict]] = None

    def chat(self, messages: List[Dict], tools: Optional[List[Dict]] = None) -> Dict:
        self.last_tools = tools
        if self.call_count < len(self.responses):
            resp = self.responses[self.call_count]
            self.call_count += 1
            return resp
        return {"content": "fallback"}


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _make_team_dir(tmp_path: Path) -> Path:
    team_dir = tmp_path / "widget"
    _write(team_dir / "TEAM.md", """---
name: widget
manager_prompt_file: manager_prompt.md
tools: []
skills: []
---
""")
    _write(team_dir / "manager_prompt.md", "You manage the widget team.")

    spec_dir = team_dir / "agents" / "specialist"
    _write(spec_dir / "AGENT.md", """---
name: specialist
role: widget-specialist
prompt_file: prompt.md
depends_on: []
tools: [echo]
skills: []
---
""")
    _write(spec_dir / "prompt.md", "You are the widget specialist.")
    return team_dir


class TestExtractVerdict:
    def test_extracts_pass(self) -> None:
        assert _extract_verdict("some text\nVERDICT: PASS\nmore") == "PASS"

    def test_extracts_stop_case_insensitive(self) -> None:
        assert _extract_verdict("verdict: stop") == "STOP"

    def test_no_verdict_returns_empty_string(self) -> None:
        assert _extract_verdict("no verdict here") == ""

    def test_empty_content_returns_empty_string(self) -> None:
        assert _extract_verdict("") == ""


class TestTagEventCallback:
    def test_none_callback_passes_through(self) -> None:
        assert _tag_event_callback(None, team="widget") is None

    def test_wraps_and_merges_tags(self) -> None:
        seen = []
        wrapped = _tag_event_callback(
            lambda et, d: seen.append((et, d)), team="widget", agent="manager",
        )
        wrapped("llm.call", {"iteration": 1})
        assert seen == [("llm.call", {"iteration": 1, "team": "widget", "agent": "manager"})]


class TestLoadAgentSpec:
    def test_parses_frontmatter_and_prompt(self, tmp_path: Path) -> None:
        team_dir = _make_team_dir(tmp_path)
        spec = load_agent_spec(team_dir / "agents" / "specialist")
        assert spec.name == "specialist"
        assert spec.role == "widget-specialist"
        assert spec.prompt == "You are the widget specialist."
        assert spec.tools == ["echo"]
        assert spec.depends_on == []

    def test_missing_prompt_file_raises(self, tmp_path: Path) -> None:
        agent_dir = tmp_path / "broken"
        _write(agent_dir / "AGENT.md", "---\nname: broken\nprompt_file: missing.md\n---\n")
        try:
            load_agent_spec(agent_dir)
            assert False, "expected FileNotFoundError"
        except FileNotFoundError:
            pass


class TestLoadTeamSpec:
    def test_discovers_agents(self, tmp_path: Path) -> None:
        team_dir = _make_team_dir(tmp_path)
        spec = load_team_spec(team_dir)
        assert spec.name == "widget"
        assert spec.manager_prompt == "You manage the widget team."
        assert set(spec.agents) == {"specialist"}

    def test_missing_team_md_raises(self, tmp_path: Path) -> None:
        try:
            load_team_spec(tmp_path / "nonexistent")
            assert False, "expected FileNotFoundError"
        except FileNotFoundError:
            pass


class TestDelegateToAgentTool:
    def test_unknown_agent_returns_error(self, tmp_path: Path) -> None:
        team_dir = _make_team_dir(tmp_path)
        spec = load_team_spec(team_dir)
        tool = DelegateToAgentTool(
            spec.agents, full_registry=ToolRegistry(), llm=FakeLLM(),
        )
        result = json.loads(tool.execute(agent_name="nope", task="x"))
        assert result["status"] == "error"
        assert "nope" in result["error"]

    def test_successful_delegation_returns_bounded_result(self, tmp_path: Path) -> None:
        team_dir = _make_team_dir(tmp_path)
        spec = load_team_spec(team_dir)
        full_registry = ToolRegistry()
        full_registry.register(EchoTool())
        llm = FakeLLM([{"content": "specialist done."}])

        tool = DelegateToAgentTool(spec.agents, full_registry=full_registry, llm=llm)
        result = json.loads(tool.execute(agent_name="specialist", task="do the thing"))

        assert result == {"status": "completed", "agent": "specialist", "content": "specialist done."}


class TestTeamManagerRun:
    def _full_registry(self) -> ToolRegistry:
        r = ToolRegistry()
        r.register(EchoTool())
        return r

    def test_end_to_end_delegation_and_verdict(self, tmp_path: Path) -> None:
        team_dir = _make_team_dir(tmp_path)
        llm = FakeLLM([
            # 1. manager's first call: delegate to the specialist
            {
                "content": "",
                "tool_calls": [{
                    "id": "call_1",
                    "function": {
                        "name": "delegate_to_agent",
                        "arguments": json.dumps({"agent_name": "specialist", "task": "investigate"}),
                    },
                }],
            },
            # 2. specialist's own single call: finishes with plain text
            {"content": "specialist findings: all good."},
            # 3. manager's second call: final answer with a verdict
            {"content": "Summary of findings.\nVERDICT: PASS\nREASONING: looks solid."},
        ])

        events: list[tuple[str, dict]] = []
        manager = TeamManager(
            team_dir,
            full_registry=self._full_registry(),
            llm=llm,
            event_callback=lambda et, d: events.append((et, d)),
        )
        result = manager.run("investigate the widget")

        assert result["status"] == "completed"
        assert "VERDICT: PASS" in result["content"]
        assert llm.call_count == 3

        # Events from both the manager's own loop and the specialist's
        # sub-loop should be tagged distinctly, not indistinguishable.
        manager_events = [d for _, d in events if d.get("role") == "manager"]
        specialist_events = [d for _, d in events if d.get("agent") == "specialist"]
        assert manager_events, "expected at least one manager-tagged event"
        assert specialist_events, "expected at least one specialist-tagged event"
        assert all(d.get("team") == "widget" for _, d in events)

    def test_run_store_records_run_and_task_lifecycle(self, tmp_path: Path) -> None:
        team_dir = _make_team_dir(tmp_path)
        llm = FakeLLM([
            {
                "content": "",
                "tool_calls": [{
                    "id": "call_1",
                    "function": {
                        "name": "delegate_to_agent",
                        "arguments": json.dumps({"agent_name": "specialist", "task": "investigate"}),
                    },
                }],
            },
            {"content": "specialist findings."},
            {"content": "VERDICT: STOP\nREASONING: not confident."},
        ])

        calls: list[tuple[str, tuple, dict]] = []

        class FakeRun:
            run_id = "run-123"

        class FakeTask:
            task_id = "task-456"

        class FakeRunStore:
            def create_run(self, *a, **kw):
                calls.append(("create_run", a, kw))
                return FakeRun()

            def mark_running(self, *a, **kw):
                calls.append(("mark_running", a, kw))

            def mark_done(self, *a, **kw):
                calls.append(("mark_done", a, kw))

            def mark_failed(self, *a, **kw):
                calls.append(("mark_failed", a, kw))

            def add_task(self, *a, **kw):
                calls.append(("add_task", a, kw))
                return FakeTask()

            def mark_task_running(self, *a, **kw):
                calls.append(("mark_task_running", a, kw))

            def mark_task_completed(self, *a, **kw):
                calls.append(("mark_task_completed", a, kw))

            def mark_task_failed(self, *a, **kw):
                calls.append(("mark_task_failed", a, kw))

        manager = TeamManager(
            team_dir,
            full_registry=self._full_registry(),
            llm=llm,
            run_store=FakeRunStore(),
            triggered_by_session_id="sess-1",
        )
        result = manager.run("investigate")

        names = [c[0] for c in calls]
        assert names == [
            "create_run", "mark_running", "add_task", "mark_task_running",
            "mark_task_completed", "mark_done",
        ]
        create_call = calls[0]
        assert create_call[1][0] == "widget"
        assert create_call[2]["triggered_by_session_id"] == "sess-1"

        mark_done_call = calls[-1]
        assert mark_done_call[2]["verdict"] == "STOP"
        assert result["run_id"] == "run-123"

    def test_runs_without_run_store_or_callback(self, tmp_path: Path) -> None:
        team_dir = _make_team_dir(tmp_path)
        llm = FakeLLM([{"content": "VERDICT: PASS"}])
        manager = TeamManager(team_dir, full_registry=self._full_registry(), llm=llm)
        result = manager.run("simple task, no delegation needed")
        assert result["status"] == "completed"
        assert "run_id" not in result

    def test_llm_call_store_tags_manager_and_specialist_calls_distinctly(self, tmp_path: Path) -> None:
        team_dir = _make_team_dir(tmp_path)
        llm = FakeLLM([
            {
                "content": "",
                "tool_calls": [{
                    "id": "call_1",
                    "function": {
                        "name": "delegate_to_agent",
                        "arguments": json.dumps({"agent_name": "specialist", "task": "investigate"}),
                    },
                }],
            },
            {"content": "specialist findings."},
            {"content": "VERDICT: PASS"},
        ])

        class FakeCallStore:
            def __init__(self):
                self.records = []

            def record(self, record):
                self.records.append(record)

        call_store = FakeCallStore()
        manager = TeamManager(
            team_dir,
            full_registry=self._full_registry(),
            llm=llm,
            llm_call_store=call_store,
            triggered_by_session_id="sess-1",
        )
        manager.run("investigate the widget")

        assert len(call_store.records) == 3
        manager_records = [r for r in call_store.records if r.tier == "manager"]
        specialist_records = [r for r in call_store.records if r.tier == "specialist"]
        assert len(manager_records) == 2
        assert len(specialist_records) == 1
        assert all(r.team == "widget" for r in call_store.records)
        assert all(r.session_id == "sess-1" for r in call_store.records)
        assert specialist_records[0].agent == "specialist"
        assert specialist_records[0].role == "widget-specialist"
