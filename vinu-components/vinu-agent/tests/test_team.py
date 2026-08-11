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


def _make_research_team_dir(tmp_path: Path) -> Path:
    """A minimal team named 'research' -- the specific name the artifact-
    writing hook in TeamManager.run() checks for (see agent/team.py). No
    specialist delegation needed for these tests; the manager answers the
    task directly in one call."""
    team_dir = tmp_path / "research"
    _write(team_dir / "TEAM.md", """---
name: research
manager_prompt_file: manager_prompt.md
tools: []
skills: []
---
""")
    _write(team_dir / "manager_prompt.md", "You manage the research team.")
    return team_dir


_RESEARCH_PASS_CONTENT = """Verdict: PASS.

```json
{"verdict": "PASS", "symbol": "AAPL", "sharpe": 0.9, "max_drawdown": -0.1, "strategy_code": "class Strategy:\\n    pass"}
```
"""


class TestResearchArtifactHook:
    """TeamManager.run()'s research-specific hook (agent/team.py) --
    writes a real vinu-research Artifact when the research team's own
    manager reaches PASS, so OrderGuard's active-artifact check actually
    sees it. See New-talk-agents/implementation/13-*.md."""

    def _full_registry(self) -> ToolRegistry:
        return ToolRegistry()

    def test_pass_writes_artifact_and_attaches_id_to_result(self, tmp_path: Path) -> None:
        from vinu_research.storage.strategy_store import SqliteStrategyStore
        import tempfile

        team_dir = _make_research_team_dir(tmp_path)
        llm = FakeLLM([{"content": _RESEARCH_PASS_CONTENT}])

        store_path = Path(tempfile.mktemp(suffix=".db"))
        strategy_store = SqliteStrategyStore(store_path)

        class FakeRun:
            run_id = "run-abc"

        class FakeRunStore:
            def __init__(self):
                self.mark_done_calls = []
                self.related_artifact_calls = []

            def create_run(self, *a, **kw):
                return FakeRun()

            def mark_running(self, *a, **kw):
                pass

            def mark_done(self, *a, **kw):
                self.mark_done_calls.append((a, kw))

            def mark_failed(self, *a, **kw):
                pass

            def set_related_artifact_id(self, run_id, artifact_id):
                self.related_artifact_calls.append((run_id, artifact_id))

        run_store = FakeRunStore()
        manager = TeamManager(
            team_dir,
            full_registry=self._full_registry(),
            llm=llm,
            run_store=run_store,
            strategy_store=strategy_store,
        )
        result = manager.run("research a strategy for AAPL")

        artifacts = strategy_store.list_artifacts()
        assert len(artifacts) == 1
        assert artifacts[0].universe == ["AAPL"]

        result_json = run_store.mark_done_calls[0][1]["result_json"]
        assert result_json["artifact_id"] == artifacts[0].artifact_id

        assert run_store.related_artifact_calls == [("run-abc", artifacts[0].artifact_id)]

        strategy_store.close()
        store_path.unlink(missing_ok=True)

    def test_no_strategy_store_skips_hook_without_error(self, tmp_path: Path) -> None:
        team_dir = _make_research_team_dir(tmp_path)
        llm = FakeLLM([{"content": _RESEARCH_PASS_CONTENT}])

        manager = TeamManager(
            team_dir, full_registry=self._full_registry(), llm=llm,
        )
        result = manager.run("research a strategy for AAPL")
        assert result["status"] == "completed"

    def test_non_research_team_never_calls_the_hook(self, tmp_path: Path) -> None:
        """widget's own PASS-shaped content should not be treated as a
        research artifact -- the hook is scoped to team name == 'research'."""
        team_dir = _make_team_dir(tmp_path)
        llm = FakeLLM([{"content": _RESEARCH_PASS_CONTENT}])

        class FakeRun:
            run_id = "run-xyz"

        class FakeRunStore:
            def create_run(self, *a, **kw):
                return FakeRun()

            def mark_running(self, *a, **kw):
                pass

            def mark_done(self, *a, **kw):
                pass

            def mark_failed(self, *a, **kw):
                pass

        class ExplodingStore:
            def upsert_artifact(self, *a, **kw):
                raise AssertionError("should never be called for a non-research team")

        manager = TeamManager(
            team_dir,
            full_registry=ToolRegistry(),
            llm=llm,
            run_store=FakeRunStore(),
            strategy_store=ExplodingStore(),
        )
        result = manager.run("investigate the widget")
        assert result["status"] == "completed"


def _make_risk_gatekeeper_team_dir(tmp_path: Path) -> Path:
    """A minimal team named 'risk_gatekeeper' -- the specific name the
    apply_risk_gatekeeper_verdict hook in TeamManager.run() checks for (see
    agent/team.py::_apply_team_result_hook)."""
    team_dir = tmp_path / "risk_gatekeeper"
    _write(team_dir / "TEAM.md", """---
name: risk_gatekeeper
manager_prompt_file: manager_prompt.md
tools: []
skills: []
---
""")
    _write(team_dir / "manager_prompt.md", "You manage the risk_gatekeeper team.")
    return team_dir


def _approved_content(artifact_id: str, approved_size: float = 15000.0) -> str:
    return f"""Verdict: APPROVED.

```json
{{"verdict": "APPROVED", "artifact_id": "{artifact_id}", "reason": "within limits", "approved_size": {approved_size}}}
```
"""


_REJECTED_CONTENT = """Verdict: REJECTED.

```json
{"verdict": "REJECTED", "artifact_id": "art_whatever", "reason": "too concentrated"}
```
"""


class TestRiskGatekeeperHook:
    """TeamManager.run()'s risk_gatekeeper-specific hook (agent/team.py) --
    transitions a real vinu-research Artifact BENCHING -> PEND via
    SqliteStrategyStore.mark_pend() when the risk_gatekeeper team's own
    manager reaches APPROVED (Phase 2, New-talk-agents/new-thinking/
    new-restructure/phases/phase-2-funding-mechanics/ -- funding itself is
    capital_allocator's batched decision now, not this hook's). See
    agent/risk_gatekeeper_hook.py."""

    def _full_registry(self) -> ToolRegistry:
        return ToolRegistry()

    def _benching_artifact(self, strategy_store) -> str:
        from vinu_research.models import Artifact, ArtifactStatus
        artifact = Artifact.create("strategy", "AAPL-test", universe=["AAPL"])
        artifact.status = ArtifactStatus.BENCHING
        strategy_store.upsert_artifact(artifact)
        return artifact.artifact_id

    def test_approved_transitions_artifact_to_pend_not_active(self, tmp_path: Path) -> None:
        from vinu_research.models import ArtifactStatus
        from vinu_research.storage.strategy_store import SqliteStrategyStore
        import tempfile

        team_dir = _make_risk_gatekeeper_team_dir(tmp_path)
        store_path = Path(tempfile.mktemp(suffix=".db"))
        strategy_store = SqliteStrategyStore(store_path)
        artifact_id = self._benching_artifact(strategy_store)

        llm = FakeLLM([{"content": _approved_content(artifact_id, approved_size=15000.0)}])

        class FakeRun:
            run_id = "run-rg-1"

        class FakeRunStore:
            def __init__(self):
                self.related_artifact_calls = []

            def create_run(self, *a, **kw):
                return FakeRun()

            def mark_running(self, *a, **kw):
                pass

            def mark_done(self, *a, **kw):
                pass

            def mark_failed(self, *a, **kw):
                pass

            def set_related_artifact_id(self, run_id, artifact_id):
                self.related_artifact_calls.append((run_id, artifact_id))

        run_store = FakeRunStore()
        manager = TeamManager(
            team_dir,
            full_registry=self._full_registry(),
            llm=llm,
            run_store=run_store,
            strategy_store=strategy_store,
        )
        result = manager.run(f"review artifact {artifact_id}")
        assert result["status"] == "completed"

        updated = strategy_store.get_artifact(artifact_id)
        assert updated.status == ArtifactStatus.PEND
        assert updated.approved_size == 15000.0
        assert run_store.related_artifact_calls == [("run-rg-1", artifact_id)]

        strategy_store.close()
        store_path.unlink(missing_ok=True)

    def test_ticker_ledger_row_written_on_pend_transition(self, tmp_path: Path) -> None:
        import tempfile
        from vinu_research.storage.strategy_store import SqliteStrategyStore
        from vinu_agent.storage.ticker_ledger import TickerLedgerStore

        team_dir = _make_risk_gatekeeper_team_dir(tmp_path)
        store_path = Path(tempfile.mktemp(suffix=".db"))
        ledger_path = Path(tempfile.mktemp(suffix=".db"))
        strategy_store = SqliteStrategyStore(store_path)
        ticker_ledger_store = TickerLedgerStore(ledger_path)
        artifact_id = self._benching_artifact(strategy_store)

        # The team-result hook only runs when a run_store is configured
        # (TeamManager.run() only calls _apply_team_result_hook if a real
        # db_run was created) -- a real run_store is required here, not
        # just for traceability's sake.
        class FakeRunStore:
            def create_run(self, *a, **kw):
                return type("FakeRun", (), {"run_id": "run-rg-2"})()

            def mark_running(self, *a, **kw):
                pass

            def mark_done(self, *a, **kw):
                pass

            def mark_failed(self, *a, **kw):
                pass

            def set_related_artifact_id(self, *a, **kw):
                pass

        llm = FakeLLM([{"content": _approved_content(artifact_id, approved_size=7500.0)}])
        manager = TeamManager(
            team_dir, full_registry=self._full_registry(), llm=llm,
            run_store=FakeRunStore(),
            strategy_store=strategy_store, ticker_ledger_store=ticker_ledger_store,
        )
        manager.run(f"review artifact {artifact_id}")

        events = ticker_ledger_store.get_events("AAPL")
        assert len(events) == 1
        assert events[0].stage == "risk_gatekeeper"
        assert events[0].event_type == "PEND"
        assert events[0].ref_id == artifact_id

        strategy_store.close()
        ticker_ledger_store.close()
        store_path.unlink(missing_ok=True)
        ledger_path.unlink(missing_ok=True)

    def test_rejected_writes_ticker_ledger_row_for_real_artifact(self, tmp_path: Path) -> None:
        """Phase 7 (New-talk-agents/new-thinking/new-restructure/phases/
        phase-7-significance-triage/): REJECTED must still write a
        TickerLedger row (event_type="REJECTED") even though it makes no
        status change -- Significance Triage's pattern detection needs
        this real history to query."""
        import tempfile
        from vinu_research.models import ArtifactStatus
        from vinu_research.storage.strategy_store import SqliteStrategyStore
        from vinu_agent.storage.ticker_ledger import TickerLedgerStore

        team_dir = _make_risk_gatekeeper_team_dir(tmp_path)
        store_path = Path(tempfile.mktemp(suffix=".db"))
        ledger_path = Path(tempfile.mktemp(suffix=".db"))
        strategy_store = SqliteStrategyStore(store_path)
        ticker_ledger_store = TickerLedgerStore(ledger_path)
        artifact_id = self._benching_artifact(strategy_store)

        rejected_content = f"""Verdict: REJECTED.

```json
{{"verdict": "REJECTED", "artifact_id": "{artifact_id}", "reason": "too concentrated"}}
```
"""
        class FakeRunStore:
            def create_run(self, *a, **kw):
                return type("FakeRun", (), {"run_id": "run-rg-3"})()

            def mark_running(self, *a, **kw):
                pass

            def mark_done(self, *a, **kw):
                pass

            def mark_failed(self, *a, **kw):
                pass

            def set_related_artifact_id(self, *a, **kw):
                pass

        llm = FakeLLM([{"content": rejected_content}])
        manager = TeamManager(
            team_dir, full_registry=self._full_registry(), llm=llm,
            run_store=FakeRunStore(),
            strategy_store=strategy_store, ticker_ledger_store=ticker_ledger_store,
        )
        manager.run(f"review artifact {artifact_id}")

        assert strategy_store.get_artifact(artifact_id).status == ArtifactStatus.BENCHING  # unchanged
        events = ticker_ledger_store.get_events("AAPL")
        assert len(events) == 1
        assert events[0].stage == "risk_gatekeeper"
        assert events[0].event_type == "REJECTED"
        assert events[0].ref_id == artifact_id
        assert events[0].text == "too concentrated"

        strategy_store.close()
        ticker_ledger_store.close()
        store_path.unlink(missing_ok=True)
        ledger_path.unlink(missing_ok=True)

    def test_rejected_leaves_artifact_untouched(self, tmp_path: Path) -> None:
        from vinu_research.models import ArtifactStatus
        from vinu_research.storage.strategy_store import SqliteStrategyStore
        import tempfile

        team_dir = _make_risk_gatekeeper_team_dir(tmp_path)
        store_path = Path(tempfile.mktemp(suffix=".db"))
        strategy_store = SqliteStrategyStore(store_path)
        artifact_id = self._benching_artifact(strategy_store)

        llm = FakeLLM([{"content": _REJECTED_CONTENT}])
        manager = TeamManager(
            team_dir, full_registry=self._full_registry(), llm=llm, strategy_store=strategy_store,
        )
        manager.run(f"review artifact {artifact_id}")

        assert strategy_store.get_artifact(artifact_id).status == ArtifactStatus.BENCHING

        strategy_store.close()
        store_path.unlink(missing_ok=True)

    def test_invalid_transition_is_swallowed_not_raised(self, tmp_path: Path) -> None:
        """An artifact that's already DISABLED (terminal) can't go to
        PEND -- mark_pend raises InvalidStatusTransition. The hook must
        swallow that, same contract as every other best-effort write in
        this codebase (broker/debrief.py)."""
        from vinu_research.models import ArtifactStatus
        from vinu_research.storage.strategy_store import SqliteStrategyStore
        import tempfile

        team_dir = _make_risk_gatekeeper_team_dir(tmp_path)
        store_path = Path(tempfile.mktemp(suffix=".db"))
        strategy_store = SqliteStrategyStore(store_path)
        artifact_id = self._benching_artifact(strategy_store)
        strategy_store.mark_disabled(artifact_id)

        llm = FakeLLM([{"content": _approved_content(artifact_id)}])
        manager = TeamManager(
            team_dir, full_registry=self._full_registry(), llm=llm, strategy_store=strategy_store,
        )
        result = manager.run(f"review artifact {artifact_id}")
        assert result["status"] == "completed"
        assert strategy_store.get_artifact(artifact_id).status == ArtifactStatus.DISABLED

        strategy_store.close()
        store_path.unlink(missing_ok=True)


def _make_capital_allocator_team_dir(tmp_path: Path) -> Path:
    """A minimal team named 'capital_allocator' -- the specific name the
    apply_capital_allocator_decision hook in TeamManager.run() checks for
    (see agent/team.py::_apply_team_result_hook)."""
    team_dir = tmp_path / "capital_allocator"
    _write(team_dir / "TEAM.md", """---
name: capital_allocator
manager_prompt_file: manager_prompt.md
tools: []
skills: []
---
""")
    _write(team_dir / "manager_prompt.md", "You manage the capital_allocator team.")
    return team_dir


def _funded_content(artifact_id: str, amount: float = 20000.0) -> str:
    return f"""Funding decision.

```json
{{"budget": 100000, "candidates": [{{"artifact_id": "{artifact_id}", "funded": true, "amount": {amount}, "reason": "within cap"}}]}}
```
"""


_NOTHING_FUNDED_CONTENT = """Nothing funded this cycle -- vinu-portfolio unreachable.

```json
{"budget": 100000, "candidates": []}
```
"""


def _unwind_content(artifact_id: str) -> str:
    return f"""Rebalance decision.

```json
{{"budget": 100000, "candidates": [], "unwind": [{{"artifact_id": "{artifact_id}", "reason": "weaker calibration"}}]}}
```
"""


class TestCapitalAllocatorHook:
    """TeamManager.run()'s capital_allocator-specific hook (agent/team.py)
    -- transitions a real vinu-research Artifact PEND -> ACTIVE via
    SqliteStrategyStore.mark_active() when the manager reports it funded
    (Phase 2). See agent/capital_allocator_hook.py."""

    def _full_registry(self) -> ToolRegistry:
        return ToolRegistry()

    def _pend_artifact(self, strategy_store) -> str:
        from vinu_research.models import Artifact, ArtifactStatus
        artifact = Artifact.create("strategy", "AAPL-test", universe=["AAPL"])
        artifact.status = ArtifactStatus.PEND
        artifact.approved_size = 25000.0
        strategy_store.upsert_artifact(artifact)
        return artifact.artifact_id

    class _FakeRunStore:
        def create_run(self, *a, **kw):
            return type("FakeRun", (), {"run_id": "run-ca-1"})()

        def mark_running(self, *a, **kw):
            pass

        def mark_done(self, *a, **kw):
            pass

        def mark_failed(self, *a, **kw):
            pass

        def set_related_artifact_id(self, *a, **kw):
            pass

    def test_funded_candidate_transitions_to_active(self, tmp_path: Path) -> None:
        from vinu_research.models import ArtifactStatus
        from vinu_research.storage.strategy_store import SqliteStrategyStore
        import tempfile

        team_dir = _make_capital_allocator_team_dir(tmp_path)
        store_path = Path(tempfile.mktemp(suffix=".db"))
        strategy_store = SqliteStrategyStore(store_path)
        artifact_id = self._pend_artifact(strategy_store)

        llm = FakeLLM([{"content": _funded_content(artifact_id, amount=20000.0)}])
        manager = TeamManager(
            team_dir, full_registry=self._full_registry(), llm=llm,
            run_store=self._FakeRunStore(), strategy_store=strategy_store,
        )
        result = manager.run(f"allocate for {artifact_id}")
        assert result["status"] == "completed"
        assert strategy_store.get_artifact(artifact_id).status == ArtifactStatus.ACTIVE

        strategy_store.close()
        store_path.unlink(missing_ok=True)

    def test_ticker_ledger_row_written_on_funded_transition(self, tmp_path: Path) -> None:
        import tempfile
        from vinu_research.storage.strategy_store import SqliteStrategyStore
        from vinu_agent.storage.ticker_ledger import TickerLedgerStore

        team_dir = _make_capital_allocator_team_dir(tmp_path)
        store_path = Path(tempfile.mktemp(suffix=".db"))
        ledger_path = Path(tempfile.mktemp(suffix=".db"))
        strategy_store = SqliteStrategyStore(store_path)
        ticker_ledger_store = TickerLedgerStore(ledger_path)
        artifact_id = self._pend_artifact(strategy_store)

        llm = FakeLLM([{"content": _funded_content(artifact_id, amount=20000.0)}])
        manager = TeamManager(
            team_dir, full_registry=self._full_registry(), llm=llm,
            run_store=self._FakeRunStore(), strategy_store=strategy_store,
            ticker_ledger_store=ticker_ledger_store,
        )
        manager.run(f"allocate for {artifact_id}")

        events = ticker_ledger_store.get_events("AAPL")
        assert len(events) == 1
        assert events[0].stage == "capital_allocator"
        assert events[0].event_type == "funded"
        assert events[0].ref_id == artifact_id

        strategy_store.close()
        ticker_ledger_store.close()
        store_path.unlink(missing_ok=True)
        ledger_path.unlink(missing_ok=True)

    def test_nothing_funded_leaves_artifact_pend(self, tmp_path: Path) -> None:
        from vinu_research.models import ArtifactStatus
        from vinu_research.storage.strategy_store import SqliteStrategyStore
        import tempfile

        team_dir = _make_capital_allocator_team_dir(tmp_path)
        store_path = Path(tempfile.mktemp(suffix=".db"))
        strategy_store = SqliteStrategyStore(store_path)
        artifact_id = self._pend_artifact(strategy_store)

        llm = FakeLLM([{"content": _NOTHING_FUNDED_CONTENT}])
        manager = TeamManager(
            team_dir, full_registry=self._full_registry(), llm=llm,
            run_store=self._FakeRunStore(), strategy_store=strategy_store,
        )
        manager.run(f"allocate for {artifact_id}")

        assert strategy_store.get_artifact(artifact_id).status == ArtifactStatus.PEND

        strategy_store.close()
        store_path.unlink(missing_ok=True)

    def test_invalid_transition_is_swallowed_not_raised(self, tmp_path: Path) -> None:
        """An artifact that's already ACTIVE (or otherwise not PEND) can't
        be mark_active'd again in a way that raises -- but a genuinely
        invalid source status (e.g. DISABLED) must be swallowed, same
        contract as risk_gatekeeper_hook.py."""
        from vinu_research.models import ArtifactStatus
        from vinu_research.storage.strategy_store import SqliteStrategyStore
        import tempfile

        team_dir = _make_capital_allocator_team_dir(tmp_path)
        store_path = Path(tempfile.mktemp(suffix=".db"))
        strategy_store = SqliteStrategyStore(store_path)
        artifact_id = self._pend_artifact(strategy_store)
        strategy_store.mark_disabled(artifact_id)

        llm = FakeLLM([{"content": _funded_content(artifact_id)}])
        manager = TeamManager(
            team_dir, full_registry=self._full_registry(), llm=llm,
            run_store=self._FakeRunStore(), strategy_store=strategy_store,
        )
        result = manager.run(f"allocate for {artifact_id}")
        assert result["status"] == "completed"
        assert strategy_store.get_artifact(artifact_id).status == ArtifactStatus.DISABLED

        strategy_store.close()
        store_path.unlink(missing_ok=True)

    def test_unwind_request_threads_services_config_to_vinu_live(self, tmp_path: Path) -> None:
        """End-to-end proof that TeamManager(services_config=...) actually
        reaches capital_allocator_hook.py's vinu-live POST -- not just that
        each piece works when called directly (see test_capital_allocator_
        hook.py for the hook's own unit tests)."""
        from unittest.mock import MagicMock, patch
        import tempfile
        from vinu_research.storage.strategy_store import SqliteStrategyStore

        team_dir = _make_capital_allocator_team_dir(tmp_path)
        store_path = Path(tempfile.mktemp(suffix=".db"))
        strategy_store = SqliteStrategyStore(store_path)
        artifact_id = self._pend_artifact(strategy_store)
        with patch("vinu_agent.broker.kill_switch.is_trading_halted", return_value=False):
            strategy_store.mark_active(artifact_id)

        llm = FakeLLM([{"content": _unwind_content(artifact_id)}])
        manager = TeamManager(
            team_dir, full_registry=self._full_registry(), llm=llm,
            run_store=self._FakeRunStore(), strategy_store=strategy_store,
            services_config={"vinu_live": "http://test-vinu-live:9999"},
        )

        mock_resp = MagicMock(status_code=200)
        mock_resp.raise_for_status = MagicMock()
        with patch("vinu_agent.agent.rebalance_guard.check_rebalance_allowed", return_value=True), \
             patch("httpx.post", return_value=mock_resp) as mock_post:
            manager.run(f"rebalance for {artifact_id}")

        mock_post.assert_called_once()
        assert mock_post.call_args[0][0] == "http://test-vinu-live:9999/live/trade-plan/rebalance-request"

        strategy_store.close()
        store_path.unlink(missing_ok=True)


def _make_screener_team_dir(tmp_path: Path) -> Path:
    """A minimal team named 'screener' -- the specific name the
    write_ticker_summaries hook in TeamManager.run() checks for (see
    agent/team.py)."""
    team_dir = tmp_path / "screener"
    _write(team_dir / "TEAM.md", """---
name: screener
manager_prompt_file: manager_prompt.md
tools: []
skills: []
---
""")
    _write(team_dir / "manager_prompt.md", "You manage the screener team.")
    return team_dir


_SCREENER_CONTENT = """## AAPL
12 of 28 angles have data...

```json
{
  "tickers": {
    "AAPL": {"summary": "12 of 28 angles have data...", "angles_with_data": 12, "angle_count": 28}
  }
}
```
"""


class TestScreenerSummaryHook:
    """TeamManager.run()'s screener-specific hook (agent/team.py) -- writes
    durable per-ticker summaries via TickerSummaryStore when the screener
    team's own manager completes. See
    New-talk-agents/implementation/00-status.md and
    agent/screener_summary_writer.py."""

    def _full_registry(self) -> ToolRegistry:
        return ToolRegistry()

    def test_completed_run_writes_ticker_summaries(self, tmp_path: Path) -> None:
        import tempfile
        from vinu_agent.storage.ticker_summaries import TickerSummaryStore

        team_dir = _make_screener_team_dir(tmp_path)
        llm = FakeLLM([{"content": _SCREENER_CONTENT}])

        store_path = Path(tempfile.mktemp(suffix=".db"))
        ticker_summary_store = TickerSummaryStore(store_path)

        class FakeRun:
            run_id = "run-scr-1"

        class FakeRunStore:
            def __init__(self):
                self.mark_done_calls = []

            def create_run(self, *a, **kw):
                return FakeRun()

            def mark_running(self, *a, **kw):
                pass

            def mark_done(self, *a, **kw):
                self.mark_done_calls.append((a, kw))

            def mark_failed(self, *a, **kw):
                pass

        run_store = FakeRunStore()
        manager = TeamManager(
            team_dir,
            full_registry=self._full_registry(),
            llm=llm,
            run_store=run_store,
            ticker_summary_store=ticker_summary_store,
        )
        result = manager.run("screen AAPL")
        assert result["status"] == "completed"

        summary = ticker_summary_store.get_summary("AAPL")
        assert summary is not None
        assert summary.angles_with_data == 12
        assert summary.source_run_id == "run-scr-1"

        result_json = run_store.mark_done_calls[0][1]["result_json"]
        assert result_json["tickers_written"] == ["AAPL"]

        ticker_summary_store.close()
        store_path.unlink(missing_ok=True)

    def test_no_ticker_summary_store_skips_hook_without_error(self, tmp_path: Path) -> None:
        team_dir = _make_screener_team_dir(tmp_path)
        llm = FakeLLM([{"content": _SCREENER_CONTENT}])

        manager = TeamManager(team_dir, full_registry=self._full_registry(), llm=llm)
        result = manager.run("screen AAPL")
        assert result["status"] == "completed"

    def test_non_screener_team_never_calls_the_hook(self, tmp_path: Path) -> None:
        team_dir = _make_team_dir(tmp_path)
        llm = FakeLLM([{"content": _SCREENER_CONTENT}])

        class ExplodingStore:
            def upsert_summary(self, *a, **kw):
                raise AssertionError("should never be called for a non-screener team")

        manager = TeamManager(
            team_dir, full_registry=ToolRegistry(), llm=llm, ticker_summary_store=ExplodingStore(),
        )
        result = manager.run("investigate the widget")
        assert result["status"] == "completed"
