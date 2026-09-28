"""item #17's "confirmed gap, not a new item": confirms the real
`/simulate/custom` route handler actually stamps
request_schema_version/response_schema_version on every response, not
just that CustomSimulateResponse *can* carry those fields (see
vinu-research's test_simulator_contract.py for the pinned-value half of
this fix)."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pandas as pd
import pytest

from vinu_simulator.models.simulation import SimulationResult
from vinu_simulator.server import routes_read
from vinu_simulator.server.schemas import (
    CUSTOM_SIMULATE_REQUEST_VERSION,
    CUSTOM_SIMULATE_RESPONSE_VERSION,
    CustomSimulateRequest,
)


def _fake_result() -> SimulationResult:
    return SimulationResult(
        strategy_name="UserStrategy",
        run_id="r1",
        timestamp=datetime.now(timezone.utc),
        config=MagicMock(),
        portfolio_values=pd.Series([1_000_000.0, 1_010_000.0]),
        daily_returns=pd.Series([0.01]),
        weights_history=pd.DataFrame(),
        trades=[],
        metrics={"sharpe_ratio": 1.0},
    )


def test_simulate_custom_route_stamps_schema_versions(monkeypatch) -> None:
    mock_service = MagicMock()
    mock_service.simulate_custom.return_value = _fake_result()
    monkeypatch.setattr(routes_read, "_get_service", lambda: mock_service)

    req = CustomSimulateRequest(
        strategy_code="class UserStrategy: ...", class_name="UserStrategy", symbols=["AAPL"],
    )
    resp = asyncio.run(routes_read.simulate_custom(req))

    assert resp.request_schema_version == CUSTOM_SIMULATE_REQUEST_VERSION
    assert resp.response_schema_version == CUSTOM_SIMULATE_RESPONSE_VERSION
    assert resp.request_schema_version != ""
    assert resp.response_schema_version != ""
