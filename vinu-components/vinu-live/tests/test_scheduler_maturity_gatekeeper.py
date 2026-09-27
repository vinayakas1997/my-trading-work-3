"""high-expectations follow-up, point #2: risk_gatekeeper consults the
system maturity tier before check_limits() runs. Off by default
(risk_gatekeeper_maturity_scaling_enabled=False) -- these tests cover both
the disabled no-op path and the enabled scaling/logging path, mocking
check_limits() itself (its own math is test_breaker.py's job) same as
test_scheduler_breaker.py does.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from vinu_live.breaker.limits import DEFAULT_LIMITS
from vinu_live.config import LiveConfig
from vinu_live.scheduler import LiveScheduler


def _make_scheduler(tmp_path, **config_overrides) -> LiveScheduler:
    config = LiveConfig(data_root=tmp_path, **config_overrides)
    scheduler = LiveScheduler(config)
    scheduler._http = MagicMock()
    return scheduler


def _resp(status_code=200, json_body=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_body if json_body is not None else {}
    return resp


class TestMaturityScaledLimits:
    @pytest.mark.asyncio
    async def test_disabled_by_default_returns_none_and_never_calls_research_api(self, tmp_path) -> None:
        scheduler = _make_scheduler(tmp_path)
        scheduler._http.get = AsyncMock(side_effect=AssertionError("should not be called"))
        result = await scheduler._maturity_scaled_limits()
        assert result is None
        assert scheduler._maturity_consultation_store.list_recent() == []

    @pytest.mark.asyncio
    async def test_enabled_and_cold_start_returns_scaled_limits_and_logs_it(self, tmp_path) -> None:
        scheduler = _make_scheduler(tmp_path, risk_gatekeeper_maturity_scaling_enabled=True)
        scheduler._http.get = AsyncMock(
            return_value=_resp(json_body={"tier": "cold_start", "n_real_trades": 0}),
        )
        result = await scheduler._maturity_scaled_limits()
        assert result is not None
        assert result.max_daily_loss_pct < DEFAULT_LIMITS.max_daily_loss_pct
        rows = scheduler._maturity_consultation_store.list_recent()
        assert len(rows) == 1
        assert rows[0]["consumer"] == "risk_gatekeeper"
        assert rows[0]["tier"] == "cold_start"
        assert rows[0]["action_taken"] == "limits_scaled_cold_start"

    @pytest.mark.asyncio
    async def test_enabled_and_mature_logs_no_change(self, tmp_path) -> None:
        scheduler = _make_scheduler(tmp_path, risk_gatekeeper_maturity_scaling_enabled=True)
        scheduler._http.get = AsyncMock(
            return_value=_resp(json_body={"tier": "mature", "n_real_trades": 500}),
        )
        result = await scheduler._maturity_scaled_limits()
        assert result == DEFAULT_LIMITS
        rows = scheduler._maturity_consultation_store.list_recent()
        assert rows[0]["action_taken"] == "no_change_already_mature"

    @pytest.mark.asyncio
    async def test_enabled_but_research_api_unreachable_fails_open_to_none(self, tmp_path) -> None:
        scheduler = _make_scheduler(tmp_path, risk_gatekeeper_maturity_scaling_enabled=True)
        scheduler._http.get = AsyncMock(side_effect=ConnectionError("boom"))
        result = await scheduler._maturity_scaled_limits()
        assert result is None
        rows = scheduler._maturity_consultation_store.list_recent()
        assert rows[0]["action_taken"] == "no_change_status_unavailable"
        assert rows[0]["tier"] == "unknown"


class TestCheckBreakerPassesScaledLimitsThrough:
    @pytest.mark.asyncio
    async def test_check_breaker_calls_check_limits_with_the_scaled_limits(self, tmp_path, monkeypatch) -> None:
        from vinu_live.breaker.engine import BreakerVerdict

        scheduler = _make_scheduler(tmp_path, risk_gatekeeper_maturity_scaling_enabled=True)
        scheduler._http.get = AsyncMock(
            return_value=_resp(json_body={"tier": "paper_only", "n_real_trades": 0}),
        )

        captured = {}

        def _fake_check_limits(*args, **kwargs):
            captured["limits"] = kwargs.get("limits")
            return BreakerVerdict.ALLOW, None

        monkeypatch.setattr("vinu_live.scheduler.check_limits", _fake_check_limits)
        await scheduler._check_breaker(portfolio_value=100_000.0)

        assert captured["limits"] is not None
        assert captured["limits"].max_daily_loss_pct == pytest.approx(DEFAULT_LIMITS.max_daily_loss_pct * 0.5)
