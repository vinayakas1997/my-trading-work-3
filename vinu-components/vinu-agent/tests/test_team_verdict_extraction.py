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
