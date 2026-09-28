"""HTTP surface for point 6's write-back path (missing-pieces-of-system/
new-theory-of-trading/system-wide-audit-and-design/reverse-engineering/
05-deciding-agent-and-precondition-tracking.md Part C): the route
vinu-live's poller calls after every real EXECUTE/SKIP
live_decision_agent verdict. Same isolated-data-root env-var pattern
test_merged_app.py already uses.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import vinu_strategy.server.routes_read as routes_read
from vinu_strategy.server.merged_app import create_merged_app


@pytest.fixture(autouse=True)
def _isolated_data_roots(tmp_path, monkeypatch):
    # routes_read._get_api() is a lazy, never-reset module-level singleton
    # -- a real, pre-existing test-isolation gap (whichever test in the
    # whole session constructs it first wins for every test after, in any
    # file, regardless of this fixture's own env vars). Reset both before
    # AND after this file's own tests (not just before) -- resetting only
    # before would leave this file's own real, populated singleton
    # dangling for whichever test file happens to run next, breaking
    # e.g. test_merged_app.py's "empty registry" assumption if it runs
    # after this file. Scoped to this file's own tests, not a fix to that
    # broader gap.
    routes_read._api = None
    monkeypatch.setenv("VINU_STRATEGY_DATA_ROOT", str(tmp_path / "strategy"))
    monkeypatch.setenv("VINU_SIMULATOR_DATA_ROOT", str(tmp_path / "simulator"))
    strategies_dir = tmp_path / "strategy" / "strategies"
    strategies_dir.mkdir(parents=True)
    (strategies_dir / "sma_cross.yaml").write_text(
        "name: sma_cross\n"
        "description: test\n"
        "schedule: 15m\n"
        "precondition:\n"
        "  description: market should be quiet before the cross\n"
        "  defined: true\n"
    )
    monkeypatch.setenv("VINU_STRATEGY_STRATEGIES_DIR", str(strategies_dir))
    yield
    routes_read._api = None


@pytest.fixture
def client() -> TestClient:
    with TestClient(create_merged_app()) as c:
        yield c


class TestPreconditionCheckRoute:
    def test_get_strategy_defaults_precondition_tested_to_false(self, client: TestClient) -> None:
        resp = client.get("/strategy/strategies/sma_cross")
        assert resp.status_code == 200
        assert resp.json()["precondition"]["tested"] is False

    def test_posting_a_check_flips_tested_and_is_visible_on_next_get(self, client: TestClient) -> None:
        resp = client.post(
            "/strategy/strategies/sma_cross/precondition-check",
            json={"precondition_held": True},
        )
        assert resp.status_code == 200
        assert resp.json()["precondition"]["tested"] is True
        assert resp.json()["precondition"]["precondition_held"] is True

        followup = client.get("/strategy/strategies/sma_cross")
        assert followup.json()["precondition"]["tested"] is True
        assert followup.json()["precondition"]["precondition_held"] is True

    def test_unknown_strategy_is_a_404(self, client: TestClient) -> None:
        resp = client.post(
            "/strategy/strategies/ghost/precondition-check",
            json={"precondition_held": True},
        )
        assert resp.status_code == 404

    def test_precondition_held_omitted_defaults_to_none_but_still_tested(self, client: TestClient) -> None:
        resp = client.post("/strategy/strategies/sma_cross/precondition-check", json={})
        assert resp.status_code == 200
        body = resp.json()
        assert body["precondition"]["tested"] is True
        assert body["precondition"]["precondition_held"] is None
