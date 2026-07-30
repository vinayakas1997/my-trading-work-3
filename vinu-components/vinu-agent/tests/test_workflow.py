from __future__ import annotations

from vinu_agent.agent.workflow import WorkflowTracker


class TestWorkflowTracker:
    def test_empty_on_init(self) -> None:
        tracker = WorkflowTracker()
        assert tracker.get_summary() == "No workflow planned."
        assert tracker.to_context_block() == ""

    def test_plan_sets_steps(self) -> None:
        tracker = WorkflowTracker()
        msg = tracker.plan(["skill-a", "skill-b"])
        assert "2 step(s)" in msg
        summary = tracker.get_summary()
        assert "skill-a" in summary
        assert "skill-b" in summary

    def test_first_step_is_active(self) -> None:
        tracker = WorkflowTracker()
        tracker.plan(["skill-a", "skill-b"])
        assert tracker._steps[0].status == "active"
        assert tracker._steps[1].status == "pending"

    def test_complete_current_moves_to_next(self) -> None:
        tracker = WorkflowTracker()
        tracker.plan(["skill-a", "skill-b"])
        msg = tracker.complete_current()
        assert "Next step: skill-b" in msg
        assert tracker._steps[0].status == "completed"
        assert tracker._steps[1].status == "active"

    def test_complete_all_steps(self) -> None:
        tracker = WorkflowTracker()
        tracker.plan(["skill-a"])
        tracker.complete_current()
        assert tracker.all_completed() is True

    def test_context_block(self) -> None:
        tracker = WorkflowTracker()
        tracker.plan(["skill-a", "skill-b"])
        block = tracker.to_context_block()
        assert "<workflow>" in block
        assert "skill-a" in block
        assert "skill-b" in block
        assert "<-- CURRENT" in block

    def test_complete_with_no_plan(self) -> None:
        tracker = WorkflowTracker()
        assert tracker.complete_current() == "No active step to complete."
