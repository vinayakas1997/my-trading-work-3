"""End-to-end integration test for Step 06: a real build_registry() +
AgentLoop run, wired the same way vinu_agent/session/service.py wires
them, exercising plan_workflow/load_skill/complete_step and confirming
their effects (including the DI fix from Step 06's blocking bug)."""
from pathlib import Path
from typing import Any, Dict, List, Optional

from vinu_agent.agent.loop import AgentLoop
from vinu_agent.agent.skills import SkillsLoader
from vinu_agent.agent.workflow import WorkflowTracker
from vinu_agent.tools import build_registry

SKILLS_DIR = Path(__file__).parent.parent / "skills"


class ScriptedLLM:
    def __init__(self, responses: List[Dict]):
        self.responses = responses
        self.call_count = 0
        self.messages_seen: List[List[Dict]] = []

    def chat(self, messages: List[Dict], tools: Optional[List[Dict]] = None) -> Dict:
        self.messages_seen.append(messages)
        resp = self.responses[min(self.call_count, len(self.responses) - 1)]
        self.call_count += 1
        return resp


def _tool_call(call_id: str, name: str, arguments: str) -> Dict:
    return {"id": call_id, "function": {"name": name, "arguments": arguments}}


class TestAgentSkillsAndWorkflowEndToEnd:
    def _build(self):
        skills_loader = SkillsLoader(skills_dir=SKILLS_DIR)
        workflow_tracker = WorkflowTracker()
        registry = build_registry(skills_loader=skills_loader, workflow_tracker=workflow_tracker)
        return skills_loader, workflow_tracker, registry

    def test_plan_load_complete_cycle_updates_workflow_context(self) -> None:
        skills_loader, workflow_tracker, registry = self._build()
        assert skills_loader.get_content("agent-self") is not None, (
            "fixture assumption: agent-self skill must exist on disk for this test"
        )

        llm = ScriptedLLM([
            {
                "content": "",
                "tool_calls": [_tool_call("c1", "plan_workflow", '{"skills": ["agent-self"]}')],
            },
            {
                "content": "",
                "tool_calls": [_tool_call("c2", "load_skill", '{"name": "agent-self"}')],
            },
            {
                "content": "",
                "tool_calls": [_tool_call("c3", "complete_step", "{}")],
            },
            {"content": "Workflow complete."},
        ])
        loop = AgentLoop(registry=registry, llm=llm, max_iterations=10)
        loop._workflow_tracker = workflow_tracker

        result = loop.run([{"role": "user", "content": "Plan and run agent-self."}])

        assert result["status"] == "completed"
        assert result["content"] == "Workflow complete."

        # plan_workflow actually registered a step on the shared tracker.
        assert workflow_tracker.all_completed()

        # load_skill actually returned real file content, not the DI-bug
        # "not available" error — this is the exact failure mode Step 06's
        # blocking bug produced before build_registry()'s injection was fixed.
        tool_messages = [m for m in result["history"] if m.get("role") == "tool"]
        load_skill_result = next(m for m in tool_messages if m["name"] == "load_skill")
        assert '"status": "error"' not in load_skill_result["content"]
        assert "Agent Identity" in load_skill_result["content"]

        # The <workflow> context block the loop injects each iteration
        # reflects the completed step, proving the loop's tracker and the
        # tools' injected tracker are the same instance, not two copies.
        final_block = workflow_tracker.to_context_block()
        assert "agent-self: completed" in final_block

        # Confirm the loop actually injected a workflow block into at least
        # one LLM call while the workflow was still active (not just that
        # the tracker object ended up correct after the fact).
        assert any(
            any(m.get("content", "").startswith("<workflow>") for m in call)
            for call in llm.messages_seen
        )

    def test_load_skill_without_injection_reports_unavailable(self) -> None:
        # Sanity check on the failure mode itself: a registry built with no
        # skills_loader must fail cleanly, not silently succeed.
        registry = build_registry()
        tool = registry.get("load_skill")
        result = tool.execute(name="agent-self")
        assert '"status": "error"' in result
        assert "not available" in result
