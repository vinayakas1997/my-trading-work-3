from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from vinu_live.breaker.limits import DEFAULT_LIMITS
from vinu_live.maturity_link import fetch_maturity_status, scale_limits_for_tier


def _resp(status_code=200, json_body=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_body if json_body is not None else {}
    return resp


class TestFetchMaturityStatus:
    @pytest.mark.asyncio
    async def test_returns_body_on_200(self) -> None:
        http = MagicMock()
        http.get = AsyncMock(return_value=_resp(json_body={"tier": "early_live", "n_real_trades": 5}))
        result = await fetch_maturity_status(http, "http://research-api")
        assert result == {"tier": "early_live", "n_real_trades": 5}

    @pytest.mark.asyncio
    async def test_fails_open_to_none_on_non_200(self) -> None:
        http = MagicMock()
        http.get = AsyncMock(return_value=_resp(status_code=503))
        assert await fetch_maturity_status(http, "http://research-api") is None

    @pytest.mark.asyncio
    async def test_fails_open_to_none_on_exception(self) -> None:
        http = MagicMock()
        http.get = AsyncMock(side_effect=ConnectionError("boom"))
        assert await fetch_maturity_status(http, "http://research-api") is None

    @pytest.mark.asyncio
    async def test_fails_open_to_none_on_malformed_body(self) -> None:
        http = MagicMock()
        http.get = AsyncMock(return_value=_resp(json_body={"unexpected": "shape"}))
        assert await fetch_maturity_status(http, "http://research-api") is None


class TestScaleLimitsForTier:
    def test_mature_returns_the_same_unscaled_limits(self) -> None:
        assert scale_limits_for_tier(DEFAULT_LIMITS, "mature") == DEFAULT_LIMITS

    def test_cold_start_scales_every_numeric_field_down(self) -> None:
        scaled = scale_limits_for_tier(DEFAULT_LIMITS, "cold_start")
        assert scaled.max_daily_loss_pct == pytest.approx(DEFAULT_LIMITS.max_daily_loss_pct * 0.25)
        assert scaled.max_var_95_pct == pytest.approx(DEFAULT_LIMITS.max_var_95_pct * 0.25)
        assert scaled.max_cluster_exposure_pct == pytest.approx(DEFAULT_LIMITS.max_cluster_exposure_pct * 0.25)

    def test_never_scales_position_count_below_one(self) -> None:
        from dataclasses import replace
        tiny_limits = replace(DEFAULT_LIMITS, max_position_count=2)
        scaled = scale_limits_for_tier(tiny_limits, "cold_start")
        assert scaled.max_position_count >= 1

    def test_never_scales_leverage_below_one(self) -> None:
        scaled = scale_limits_for_tier(DEFAULT_LIMITS, "cold_start")
        assert scaled.max_leverage >= 1.0

    def test_does_not_mutate_the_input(self) -> None:
        before = DEFAULT_LIMITS.max_daily_loss_pct
        scale_limits_for_tier(DEFAULT_LIMITS, "cold_start")
        assert DEFAULT_LIMITS.max_daily_loss_pct == before

    def test_unknown_tier_fails_open_to_unscaled(self) -> None:
        assert scale_limits_for_tier(DEFAULT_LIMITS, "some_future_tier") == DEFAULT_LIMITS
