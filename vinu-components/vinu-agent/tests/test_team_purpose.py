from pathlib import Path
from types import SimpleNamespace

from vinu_infra.llm.identity import bind_context, current_purpose, purpose_scope

from vinu_agent.agent.team import TEAM_PURPOSE, TeamManager

TEAMS_DIR = Path(__file__).resolve().parents[1] / "teams"


def test_every_listed_team_exists():
    teams = {p.name for p in TEAMS_DIR.iterdir() if p.is_dir()}
    assert set(TEAM_PURPOSE) <= teams, f"unknown teams: {set(TEAM_PURPOSE) - teams}"


def test_live_decision_team_runs_under_the_live_decision_purpose():
    manager = TeamManager.__new__(TeamManager)
    manager.spec = SimpleNamespace(name="live_decision")
    manager._run = lambda task, context=None: current_purpose()
    assert manager.run("go") == "live_decision"
    assert current_purpose() is None                      # and it does not leak out afterwards


def test_an_unlisted_team_sets_no_purpose():
    manager = TeamManager.__new__(TeamManager)
    manager.spec = SimpleNamespace(name="some_new_team")
    manager._run = lambda task, context=None: current_purpose()
    assert manager.run("go") is None


def test_purpose_survives_a_worker_thread_only_when_bound():
    from concurrent.futures import ThreadPoolExecutor

    with purpose_scope("live_decision"), ThreadPoolExecutor(max_workers=1) as pool:
        assert pool.submit(current_purpose).result() is None                                   # the trap
        assert pool.submit(bind_context(current_purpose)).result() == "live_decision"          # the fix
