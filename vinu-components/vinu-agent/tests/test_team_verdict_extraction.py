"""`SELF-VERDICT: PASS` (the backtest runner's own note about its sweep evidence) contains the text "VERDICT: PASS". The
old pattern read it as the team's final verdict, so a research run was recorded as PASS with the risk critic never
having been consulted."""
import pytest

from vinu_agent.agent.team import _extract_verdict


@pytest.mark.parametrize("text, expected", [
    ("The backtest completed with a SELF-VERDICT: PASS. Now I need to send this to the risk_critic.", ""),
    ("SELF-VERDICT: PASS\nSharpe 0.6", ""),
    ("self-verdict: pass", ""),
    ("risk review done.\nVERDICT: PASS", "PASS"),
    ("**VERDICT: STOP** because the drawdown is too deep", "STOP"),
    ("VERDICT: **PASS**", "PASS"),
    ("verdict: stop", "STOP"),
    ("", ""),
    ("no decision here", ""),
])
def test_only_a_standalone_verdict_line_counts(text, expected):
    assert _extract_verdict(text) == expected


def test_the_last_verdict_wins_not_an_earlier_quotation():
    assert _extract_verdict("risk_critic said VERDICT: PASS earlier.\n...\nFinal answer.\nVERDICT: STOP") == "STOP"
    assert _extract_verdict("SELF-VERDICT: PASS\n...\nVERDICT: STOP") == "STOP"


class _Loop:
    def __init__(self, outputs, seen):
        self.outputs, self.seen = outputs, seen

    def run(self, messages):
        self.seen.append(list(messages))
        return self.outputs.pop(0)


def _factory(outputs, seen):
    return lambda: _Loop(outputs, seen)


def test_a_manager_that_stops_before_the_risk_critic_is_asked_to_continue():
    from vinu_agent.agent.team import run_until_verdict

    seen = []
    outputs = [
        {"status": "completed", "content": "SELF-VERDICT: PASS. Now I need to send this to the risk_critic."},
        {"status": "completed", "content": "risk_critic reviewed it.\nVERDICT: STOP"},
    ]
    result = run_until_verdict(_factory(outputs, seen), [{"role": "user", "content": "task"}], required=True)
    assert _extract_verdict(result["content"]) == "STOP" and len(seen) == 2
    resumed = seen[1]
    assert resumed[-2] == {"role": "assistant", "content": "SELF-VERDICT: PASS. Now I need to send this to the risk_critic."}
    assert "risk_critic" in resumed[-1]["content"] and resumed[-1]["role"] == "user"


def test_a_manager_that_already_decided_is_left_alone():
    from vinu_agent.agent.team import run_until_verdict

    seen = []
    result = run_until_verdict(_factory([{"status": "completed", "content": "VERDICT: PASS"}], seen), [], required=True)
    assert len(seen) == 1 and result["content"] == "VERDICT: PASS"


def test_nudging_is_bounded_and_skipped_for_teams_that_need_no_verdict():
    from vinu_agent.agent.team import run_until_verdict

    forever = lambda: [{"status": "completed", "content": "still thinking"} for _ in range(10)]
    seen = []
    run_until_verdict(_factory(forever(), seen), [], required=True, max_nudges=2)
    assert len(seen) == 3                       # the first run plus two nudges, then it gives up
    seen = []
    run_until_verdict(_factory(forever(), seen), [], required=False)
    assert len(seen) == 1


def test_a_failed_run_is_not_nudged():
    from vinu_agent.agent.team import run_until_verdict

    seen = []
    run_until_verdict(_factory([{"status": "error", "content": "boom"}], seen), [], required=True)
    assert len(seen) == 1


class TestMinimumAttemptsBeforeGivingUp:
    """A research manager gave up after ONE attempt ("I've reached the maximum number of iterations") having used 2 of
    its 25 turns. The process is: at least N distinct candidate strategies, each fed the previous failures, before STOP."""

    def _stop(self, text="gave up.\nVERDICT: STOP"):
        return {"status": "completed", "content": text}

    def test_an_early_stop_is_sent_back_until_enough_attempts_were_made(self):
        from vinu_agent.agent.team import run_until_verdict

        made = {"n": 1}
        seen = []

        def make_loop():
            class L:
                def run(self, messages):
                    seen.append(list(messages))
                    if len(seen) > 1:
                        made["n"] = 3           # after the nudge the manager makes the missing attempts
                    return self_stop()
            return L()

        self_stop = self._stop
        result = run_until_verdict(
            make_loop, [{"role": "user", "content": "task"}], required=True, max_nudges=5,
            attempts=lambda: made["n"], min_attempts=3, budget=25)
        assert len(seen) == 2                   # the run, then one nudge; with 3 attempts made the next STOP is accepted
        nudge = seen[1][-1]["content"]
        assert "only 1 of the 3" in nudge and "25 turns" in nudge and "idea_generator" in nudge
        assert result["content"].endswith("VERDICT: STOP")

    def test_a_pass_ends_the_run_at_once_whatever_the_attempt_count(self):
        from vinu_agent.agent.team import run_until_verdict

        seen = []
        out = [{"status": "completed", "content": "risk_critic ok.\nVERDICT: PASS"}]
        result = run_until_verdict(_factory(out, seen), [], required=True, attempts=lambda: 1, min_attempts=3)
        assert len(seen) == 1 and result["content"].endswith("PASS")

    def test_a_stop_after_enough_attempts_is_accepted(self):
        from vinu_agent.agent.team import run_until_verdict

        seen = []
        result = run_until_verdict(_factory([self._stop()], seen), [], required=True, attempts=lambda: 3, min_attempts=3)
        assert len(seen) == 1 and result["content"].endswith("STOP")

    def test_giving_up_is_still_bounded_when_the_manager_never_complies(self):
        from vinu_agent.agent.team import run_until_verdict

        seen = []
        outputs = [self._stop() for _ in range(20)]
        run_until_verdict(_factory(outputs, seen), [], required=True, max_nudges=4, attempts=lambda: 1, min_attempts=3)
        assert len(seen) == 5                   # the run plus four nudges, then it stops pushing


def test_the_delegation_tool_counts_idea_generator_requests():
    from unittest.mock import MagicMock

    from vinu_agent.agent.team import AgentSpec, DelegateToAgentTool

    spec = AgentSpec(name="idea_generator", role="r", prompt="p")
    tool = DelegateToAgentTool({"idea_generator": spec}, full_registry=MagicMock(), llm=MagicMock())
    tool._full_registry.subset.return_value = MagicMock()
    import vinu_agent.agent.team as team_mod

    original = team_mod.AgentLoop
    try:
        team_mod.AgentLoop = lambda **kw: MagicMock(run=MagicMock(return_value={"content": "ok", "status": "completed"}))
        tool.execute(agent_name="idea_generator", task="t")
        tool.execute(agent_name="idea_generator", task="t2")
        tool.execute(agent_name="nobody", task="t3")
    finally:
        team_mod.AgentLoop = original
    assert tool.delegations == {"idea_generator": 2}        # an unknown agent is not counted
