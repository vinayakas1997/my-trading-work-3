"""item #17's own unnumbered "confirmed gap, not a new item": no contract/
schema test anywhere between agent<->research<->simulator. This is the
research<->simulator hop (see vinu-agent's own test_research_contract.py
for the agent<->research hop).

Approach, same as the agent-side test: exercise `ResearchTools.run_backtest()`'s
REAL body-building code (only `_simulator_client.post` itself is faked)
and validate the *actual* dict it sends against vinu-simulator's own real
pydantic request model -- catches drift on either side, not just a
hand-copied assumption about what the other service expects."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from vinu_infra.contract_version import contract_version
from vinu_research.tools import ResearchTools
from vinu_simulator.server.schemas import CustomSimulateRequest, CustomSimulateResponse


@pytest.fixture
def tools() -> ResearchTools:
    return ResearchTools()


class TestRunBacktestBodyMatchesRealSimulatorSchema:
    @pytest.mark.asyncio
    async def test_required_fields_only_validates(self, tools, monkeypatch) -> None:
        captured: dict = {}

        async def _fake_post(path, *, json, **kw):
            captured["path"] = path
            captured["json"] = json
            return {
                "run_id": "r1", "strategy_name": "UserStrategy",
                "metrics": {"sharpe_ratio": 1.0}, "trade_count": 5, "equity_points": 100,
            }

        monkeypatch.setattr(tools._simulator_client, "post", _fake_post)
        await tools.run_backtest(
            strategy_code="class UserStrategy: ...",
            strategy_class_name="UserStrategy",
            symbols=["AAPL"],
            from_date="2023-01-01",
            to_date="2023-12-31",
        )
        assert captured["path"] == "/simulate/custom"
        CustomSimulateRequest(**captured["json"])  # raises on any schema drift

    @pytest.mark.asyncio
    async def test_every_optional_field_set_still_validates(self, tools, monkeypatch) -> None:
        captured: dict = {}

        async def _fake_post(path, *, json, **kw):
            captured["json"] = json
            return {
                "run_id": "r1", "strategy_name": "UserStrategy",
                "metrics": {}, "trade_count": 0, "equity_points": 0,
            }

        monkeypatch.setattr(tools._simulator_client, "post", _fake_post)
        await tools.run_backtest(
            strategy_code="class UserStrategy: ...",
            strategy_class_name="UserStrategy",
            symbols=["AAPL", "MSFT"],
            from_date="2023-01-01",
            to_date="2023-12-31",
            indicators=["sma_20", "rsi_14"],
            initial_capital=50_000.0,
            transaction_cost_pct=0.001,
            slippage_pct=0.0005,
            allow_short=False,
            interval="1d",
            run_validation=False,
        )
        req = CustomSimulateRequest(**captured["json"])
        assert req.symbols == ["AAPL", "MSFT"]
        assert req.indicators == ["sma_20", "rsi_14"]
        assert req.allow_short is False


class TestRunBacktestRequiredResponseFieldsAreARealSubset:
    """run_backtest()'s own `required = [...]` list is a hardcoded
    duplicate of what it actually reads off `data` -- if vinu-simulator
    ever renamed one of these response fields, this would be the only
    thing to notice before it silently returned None."""

    def test_required_fields_are_all_real_response_fields(self) -> None:
        required = ["run_id", "strategy_name", "metrics", "trade_count", "equity_points"]
        response_fields = set(CustomSimulateResponse.model_fields.keys())
        missing = [f for f in required if f not in response_fields]
        assert missing == []


class TestPinnedContractVersion:
    """item #17's remaining "confirmed gap": the tests above catch drift
    at TEST time, when both sides' code is checked out together -- they
    can't catch DEPLOY-time drift between independently-versioned
    running services. `CustomSimulateResponse.request_schema_version`/
    `response_schema_version` (a deterministic hash, echoed on every real
    /simulate/custom response) exists for exactly that. Pinning the
    values here means this test fails LOUDLY and explicitly the moment
    either schema's shape actually changes, forcing a human to look at
    the diff and re-confirm compatibility, rather than the version
    silently drifting unnoticed in a test that only checks shape-
    equivalence and never surfaces the version number itself."""

    # Confirmed 2026-09-28 -- update these two values (and re-verify
    # vinu-research's own request/response handling still matches)
    # whenever this test fails, don't just paste in the new hash.
    _EXPECTED_REQUEST_VERSION = "ecadb41ee551"        # bumped on purpose: CustomSimulateRequest gained `session`
    _EXPECTED_RESPONSE_VERSION = "002ce5e717d7"

    def test_request_schema_version_is_pinned(self) -> None:
        assert contract_version(CustomSimulateRequest) == self._EXPECTED_REQUEST_VERSION

    def test_response_schema_version_is_pinned(self) -> None:
        assert contract_version(CustomSimulateResponse) == self._EXPECTED_RESPONSE_VERSION
