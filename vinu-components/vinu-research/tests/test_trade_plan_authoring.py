from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from vinu_research.config import ResearchConfig
from vinu_research.forecast_skill import ForecastSkillConfig
from vinu_research.models import (
    Artifact,
    ArtifactStatus,
    Forecast,
    InvalidationCondition,
    RiskBand,
    SignalEntry,
    TradePlan,
    TradeScoreResult,
)
from vinu_research.trade_plan_authoring import (
    TradePlanApprovalError,
    _normalize_summary_context,
    _regime_size_multiplier,
    approve_trade_plan,
    author_trade_plan,
    fetch_angle_signals,
    fetch_current_regime,
    fetch_debate_signal,
    fetch_options_context,
    fetch_personality_features,
    fetch_risk_state,
    freeze_trade_plan,
    record_realized_outcome,
    update_in_trade_action,
)


class _StubTools:
    """Duck-types the subset of ResearchTools trade_plan_authoring depends on."""

    def __init__(
        self,
        returns: pd.Series | None,
        angle_rows: dict[str, list[dict]],
        options_snapshot: dict | None = None,
        debate_run: dict | None = None,
    ) -> None:
        self._returns = returns
        self._angle_rows = angle_rows
        self._options_snapshot = options_snapshot
        self._debate_run = debate_run

    async def get_benchmark_data(self, symbol, from_date, to_date):
        return self._returns

    async def get_angle_rows(self, angle_name, symbol):
        return self._angle_rows.get(angle_name, [])

    async def get_options_snapshot(self, symbol):
        return self._options_snapshot

    async def get_latest_debate_run(self, preset_name, symbol):
        return self._debate_run


def _synthetic_returns(n: int = 120, seed: int = 7) -> pd.Series:
    rng = np.random.default_rng(seed)
    return pd.Series(rng.normal(loc=0.0005, scale=0.015, size=n))


def _positive_edge_returns(n: int = 100) -> pd.Series:
    """Deterministic returns with a clearly positive Kelly fraction (unlike
    _synthetic_returns' seed=7, which happens to produce kelly_fraction=0.0
    -- fine for tests that don't care about the sizing value, but useless
    for TestTradeScorePositionSizing, which needs a nonzero base size to
    observe the tier multiplier actually scaling it down."""
    values = ([0.01] * 65 + [-0.005] * 35)[:n]
    return pd.Series(values)


class _StubLlmClient:
    def __init__(self, response: dict) -> None:
        self._response = response

    async def chat_json(self, system, user, *, raise_on_failure: bool = False):
        return self._response


class TestFetchRiskState:
    async def test_insufficient_data_when_no_returns(self) -> None:
        tools = _StubTools(returns=None, angle_rows={})
        state = await fetch_risk_state(tools, "AAPL")
        assert state["status"] == "insufficient_data"

    async def test_insufficient_data_when_too_few_returns(self) -> None:
        tools = _StubTools(returns=_synthetic_returns(5), angle_rows={})
        state = await fetch_risk_state(tools, "AAPL")
        assert state["status"] == "insufficient_data"

    async def test_ok_status_has_expected_fields(self) -> None:
        tools = _StubTools(returns=_synthetic_returns(120), angle_rows={})
        state = await fetch_risk_state(tools, "AAPL")
        assert state["status"] == "ok"
        for key in (
            "annualized_volatility", "var_95_daily", "cvar_95_daily",
            "expected_move_1d_pct", "kelly_fraction", "garch_persistence",
        ):
            assert key in state


class TestFetchPersonalityFeatures:
    async def test_returns_latest_row_of_each_angle(self) -> None:
        tools = _StubTools(
            returns=None,
            angle_rows={
                "shock_personality": [{"gap_fill_rate": {"mean": 0.3}}, {"gap_fill_rate": {"mean": 0.5}}],
                "shock_clustering": [{"cluster_members": [{"symbol": "MSFT", "shock_correlation": 0.8}]}],
            },
        )
        features = await fetch_personality_features(tools, "AAPL")
        assert features["shock_personality"]["gap_fill_rate"]["mean"] == 0.5
        assert features["shock_clustering"]["cluster_members"][0]["symbol"] == "MSFT"

    async def test_empty_when_no_angle_data(self) -> None:
        tools = _StubTools(returns=None, angle_rows={})
        features = await fetch_personality_features(tools, "AAPL")
        assert features == {"shock_personality": {}, "shock_clustering": {}}


class TestNormalizeSummaryContextAngleDigest:
    """Regression for the '2 of 28 angles' gate-conflict fix: angle_digest
    must survive normalization (bounded, defense-in-depth against a
    caller from a different repo/process not already enforcing the
    bounds), and its absence must not break the existing summary-only
    path -- see high-expectations gate-conflict audit."""

    def test_angle_digest_passes_through(self) -> None:
        result = _normalize_summary_context({
            "summary": "AAPL looks constructive.",
            "angle_digest": {"trend_lifecycle": {"stage": "mature"}},
        })
        assert result["angle_digest"] == {"trend_lifecycle": {"stage": "mature"}}

    def test_missing_angle_digest_defaults_to_empty(self) -> None:
        result = _normalize_summary_context({"summary": "AAPL looks constructive."})
        assert result["angle_digest"] == {}

    def test_angle_count_is_capped(self) -> None:
        digest = {f"angle_{i}": {"v": i} for i in range(40)}
        result = _normalize_summary_context({"summary": "x", "angle_digest": digest})
        assert len(result["angle_digest"]) == 30

    def test_field_count_per_angle_is_not_capped(self) -> None:
        digest = {"angle_a": {f"f{i}": i for i in range(10)}}
        result = _normalize_summary_context({"summary": "x", "angle_digest": digest})
        assert len(result["angle_digest"]["angle_a"]) == 10

    def test_non_dict_angle_digest_fails_open_to_empty(self) -> None:
        result = _normalize_summary_context({"summary": "x", "angle_digest": "not-a-dict"})
        assert result["angle_digest"] == {}

    def test_no_summary_still_returns_none_regardless_of_digest(self) -> None:
        """The existing fail-open rule (no summary text -> None entirely)
        must not be bypassed just because a digest is present."""
        result = _normalize_summary_context({"summary": "", "angle_digest": {"a": {"x": 1}}})
        assert result is None


class TestRegimeSizeMultiplier:
    """Regime router follow-up: a second, direct channel for current_regime
    to affect a trade plan's position size, independent of its existing
    one-vote-among-many confluence signal. Mirrors vinu-portfolio's own
    _regime_alignment_multiplier tilt shape."""

    def test_bull_long_favored(self) -> None:
        assert _regime_size_multiplier("bull", "long", 0.3) == pytest.approx(1.3)

    def test_bull_short_penalized(self) -> None:
        assert _regime_size_multiplier("bull", "short", 0.3) == pytest.approx(0.7)

    def test_bear_short_favored(self) -> None:
        assert _regime_size_multiplier("bear", "short", 0.3) == pytest.approx(1.3)

    def test_bear_long_penalized(self) -> None:
        assert _regime_size_multiplier("bear", "long", 0.3) == pytest.approx(0.7)

    def test_high_vol_penalized_regardless_of_direction(self) -> None:
        assert _regime_size_multiplier("high_vol", "long", 0.3) == pytest.approx(0.7)
        assert _regime_size_multiplier("high_vol", "short", 0.3) == pytest.approx(0.7)

    def test_sideways_is_neutral(self) -> None:
        assert _regime_size_multiplier("sideways", "long", 0.3) == pytest.approx(1.0)

    def test_unmapped_regime_is_neutral(self) -> None:
        assert _regime_size_multiplier("some_new_regime", "long", 0.3) == pytest.approx(1.0)

    def test_none_regime_is_neutral(self) -> None:
        assert _regime_size_multiplier(None, "long", 0.3) == pytest.approx(1.0)

    def test_neutral_direction_is_neutral(self) -> None:
        assert _regime_size_multiplier("bull", "neutral", 0.3) == pytest.approx(1.0)

    def test_zero_bound_disables_tilt(self) -> None:
        assert _regime_size_multiplier("bull", "long", 0.0) == pytest.approx(1.0)
        assert _regime_size_multiplier("bear", "long", 0.0) == pytest.approx(1.0)


class TestFetchCurrentRegime:
    async def test_returns_regime_from_current_regime_row(self) -> None:
        tools = _StubTools(returns=None, angle_rows={
            "regime_analysis": [{"metric": "current_regime", "regime": "bull"}],
        })
        assert await fetch_current_regime(tools, "AAPL") == "bull"

    async def test_no_matching_row_returns_none(self) -> None:
        tools = _StubTools(returns=None, angle_rows={
            "regime_analysis": [{"metric": "something_else"}],
        })
        assert await fetch_current_regime(tools, "AAPL") is None

    async def test_no_regime_data_returns_none(self) -> None:
        tools = _StubTools(returns=None, angle_rows={})
        assert await fetch_current_regime(tools, "AAPL") is None

    async def test_fetch_failure_propagates(self) -> None:
        class FailingTools(_StubTools):
            async def get_angle_rows(self, angle_name, symbol):
                raise ConnectionError("angle service down")

        tools = FailingTools(returns=None, angle_rows={})
        with pytest.raises(ConnectionError):
            await fetch_current_regime(tools, "AAPL")


class TestFetchAngleSignals:
    async def test_no_angle_data_returns_no_signals(self) -> None:
        tools = _StubTools(returns=None, angle_rows={})
        signals = await fetch_angle_signals(tools, "AAPL", "long")
        assert signals == []

    async def test_trend_lifecycle_uptrend_supports_long(self) -> None:
        tools = _StubTools(returns=None, angle_rows={
            "trend_lifecycle": [{"type": "lifecycle", "stage": "uptrend"}],
        })
        signals = await fetch_angle_signals(tools, "AAPL", "long")
        assert len(signals) == 1
        assert signals[0].signal == "trend_lifecycle_stage"
        assert signals[0].direction == "supporting"

    async def test_trend_lifecycle_downtrend_contradicts_long(self) -> None:
        tools = _StubTools(returns=None, angle_rows={
            "trend_lifecycle": [{"type": "lifecycle", "stage": "downtrend"}],
        })
        signals = await fetch_angle_signals(tools, "AAPL", "long")
        assert signals[0].direction == "contradicting"

    async def test_trend_lifecycle_downtrend_supports_short(self) -> None:
        tools = _StubTools(returns=None, angle_rows={
            "trend_lifecycle": [{"type": "lifecycle", "stage": "downtrend"}],
        })
        signals = await fetch_angle_signals(tools, "AAPL", "short")
        assert signals[0].direction == "supporting"

    async def test_trend_lifecycle_sideways_produces_no_signal(self) -> None:
        tools = _StubTools(returns=None, angle_rows={
            "trend_lifecycle": [{"type": "lifecycle", "stage": "sideways"}],
        })
        signals = await fetch_angle_signals(tools, "AAPL", "long")
        assert signals == []

    async def test_regime_alignment_bull_supports_long(self) -> None:
        tools = _StubTools(returns=None, angle_rows={
            "regime_analysis": [
                {"metric": "regime_stats", "regime": "sideways", "pct_of_time": 0.7},
                {"metric": "current_regime", "regime": "bull"},
            ],
        })
        signals = await fetch_angle_signals(tools, "AAPL", "long")
        assert len(signals) == 1
        assert signals[0].signal == "current_regime_alignment"
        assert signals[0].direction == "supporting"

    async def test_regime_mismatch_contradicts(self) -> None:
        tools = _StubTools(returns=None, angle_rows={
            "regime_analysis": [{"metric": "current_regime", "regime": "bear"}],
        })
        signals = await fetch_angle_signals(tools, "AAPL", "long")
        assert signals[0].direction == "contradicting"

    async def test_no_current_regime_row_produces_no_regime_signal(self) -> None:
        # Older payloads predating the current_regime row -- fail open, no signal.
        tools = _StubTools(returns=None, angle_rows={
            "regime_analysis": [{"metric": "regime_stats", "regime": "bull", "pct_of_time": 0.6}],
        })
        signals = await fetch_angle_signals(tools, "AAPL", "long")
        assert signals == []

    async def test_backtested_win_rate_thresholds(self) -> None:
        high = await fetch_angle_signals(
            _StubTools(returns=None, angle_rows={"backtesting_44_metrics": [{"win_rate": 0.62}]}),
            "AAPL", "long",
        )
        assert any(s.signal == "backtested_win_rate" and s.direction == "supporting" for s in high)

        low = await fetch_angle_signals(
            _StubTools(returns=None, angle_rows={"backtesting_44_metrics": [{"win_rate": 0.30}]}),
            "AAPL", "long",
        )
        assert any(s.signal == "backtested_win_rate" and s.direction == "contradicting" for s in low)

        neutral = await fetch_angle_signals(
            _StubTools(returns=None, angle_rows={"backtesting_44_metrics": [{"win_rate": 0.50}]}),
            "AAPL", "long",
        )
        assert not any(s.signal == "backtested_win_rate" for s in neutral)

    async def test_backtested_profit_factor_thresholds(self) -> None:
        high = await fetch_angle_signals(
            _StubTools(returns=None, angle_rows={"backtesting_44_metrics": [{"profit_factor": 2.0}]}),
            "AAPL", "long",
        )
        assert any(s.signal == "backtested_profit_factor" and s.direction == "supporting" for s in high)

        low = await fetch_angle_signals(
            _StubTools(returns=None, angle_rows={"backtesting_44_metrics": [{"profit_factor": 0.8}]}),
            "AAPL", "long",
        )
        assert any(s.signal == "backtested_profit_factor" and s.direction == "contradicting" for s in low)

    async def test_null_profit_factor_is_skipped_not_crashed(self) -> None:
        tools = _StubTools(returns=None, angle_rows={
            "backtesting_44_metrics": [{"win_rate": 0.62, "profit_factor": None}],
        })
        signals = await fetch_angle_signals(tools, "AAPL", "long")
        assert not any(s.signal == "backtested_profit_factor" for s in signals)

    async def test_one_angle_failure_does_not_block_the_others(self) -> None:
        class _FlakyTools(_StubTools):
            async def get_angle_rows(self, angle_name, symbol):
                if angle_name == "trend_lifecycle":
                    raise ConnectionError("angle service down")
                return await super().get_angle_rows(angle_name, symbol)

        tools = _FlakyTools(returns=None, angle_rows={
            "regime_analysis": [{"metric": "current_regime", "regime": "bull"}],
        })
        signals = await fetch_angle_signals(tools, "AAPL", "long")
        assert any(s.signal == "current_regime_alignment" for s in signals)

    async def test_all_three_angles_combine(self) -> None:
        tools = _StubTools(returns=None, angle_rows={
            "trend_lifecycle": [{"type": "lifecycle", "stage": "uptrend"}],
            "regime_analysis": [{"metric": "current_regime", "regime": "bull"}],
            "backtesting_44_metrics": [{"win_rate": 0.62, "profit_factor": 2.0}],
        })
        signals = await fetch_angle_signals(tools, "AAPL", "long")
        names = {s.signal for s in signals}
        assert names == {
            "trend_lifecycle_stage", "current_regime_alignment",
            "backtested_win_rate", "backtested_profit_factor",
        }


class TestFetchDebateSignal:
    async def test_no_completed_run_returns_none(self) -> None:
        tools = _StubTools(returns=None, angle_rows={}, debate_run=None)
        assert await fetch_debate_signal(tools, "AAPL", "long") is None

    async def test_bullish_verdict_supports_long(self) -> None:
        tools = _StubTools(returns=None, angle_rows={}, debate_run={
            "status": "ok",
            "tasks": [{"agent_name": "risk_officer", "result": "Overall stance: bullish, high conviction."}],
        })
        signal = await fetch_debate_signal(tools, "AAPL", "long")
        assert signal is not None
        assert signal.signal == "investment_committee_debate"
        assert signal.direction == "supporting"

    async def test_bullish_verdict_contradicts_short(self) -> None:
        tools = _StubTools(returns=None, angle_rows={}, debate_run={
            "status": "ok",
            "tasks": [{"agent_name": "risk_officer", "result": "Overall stance: bullish."}],
        })
        signal = await fetch_debate_signal(tools, "AAPL", "short")
        assert signal.direction == "contradicting"

    async def test_bearish_verdict_supports_short(self) -> None:
        tools = _StubTools(returns=None, angle_rows={}, debate_run={
            "status": "ok",
            "tasks": [{"agent_name": "risk_officer", "result": "Bearish outlook given headwinds."}],
        })
        signal = await fetch_debate_signal(tools, "AAPL", "short")
        assert signal.direction == "supporting"

    async def test_neutral_verdict_is_neutral_regardless_of_direction(self) -> None:
        tools = _StubTools(returns=None, angle_rows={}, debate_run={
            "status": "ok",
            "tasks": [{"agent_name": "risk_officer", "result": "Neutral, conviction is low."}],
        })
        signal = await fetch_debate_signal(tools, "AAPL", "long")
        assert signal.direction == "neutral"

    async def test_unparseable_verdict_returns_none(self) -> None:
        tools = _StubTools(returns=None, angle_rows={}, debate_run={
            "status": "ok",
            "tasks": [{"agent_name": "risk_officer", "result": "Inconclusive, more data needed."}],
        })
        assert await fetch_debate_signal(tools, "AAPL", "long") is None

    async def test_falls_back_to_final_report_when_no_risk_officer_task(self) -> None:
        tools = _StubTools(returns=None, angle_rows={}, debate_run={
            "status": "ok", "tasks": [], "final_report": "Committee leans bullish overall.",
        })
        signal = await fetch_debate_signal(tools, "AAPL", "long")
        assert signal is not None
        assert signal.direction == "supporting"

    async def test_fetch_failure_fails_open(self) -> None:
        class _FailingTools(_StubTools):
            async def get_latest_debate_run(self, preset_name, symbol):
                raise ConnectionError("agent service down")

        tools = _FailingTools(returns=None, angle_rows={})
        # fetch_debate_signal itself doesn't catch -- author_trade_plan's
        # caller does (matching fetch_angle_signals' own try/except at the
        # call site) -- so this asserts the exception propagates from here,
        # confirming the fail-open behavior lives at the call site.
        with pytest.raises(ConnectionError):
            await fetch_debate_signal(tools, "AAPL", "long")


class TestDebateConvictionStrength:
    """fetch_debate_signal's strength used to be a flat 0.5 regardless of
    how strongly the risk_officer's text read -- debate_conviction_strength
    now derives a tier from simple intensity language, reused by
    fetch_debate_signal (entry weighting) and the in-trade thesis re-check."""

    async def test_strong_language_yields_top_tier(self) -> None:
        tools = _StubTools(returns=None, angle_rows={}, debate_run={
            "status": "ok",
            "tasks": [{"agent_name": "risk_officer", "result": "Strongly bullish, clear breakout."}],
        })
        signal = await fetch_debate_signal(tools, "AAPL", "long")
        assert signal.strength == pytest.approx(1.0)

    async def test_plain_language_yields_middle_tier(self) -> None:
        tools = _StubTools(returns=None, angle_rows={}, debate_run={
            "status": "ok",
            "tasks": [{"agent_name": "risk_officer", "result": "Bullish."}],
        })
        signal = await fetch_debate_signal(tools, "AAPL", "long")
        assert signal.strength == pytest.approx(0.7)

    async def test_weak_language_yields_bottom_tier(self) -> None:
        tools = _StubTools(returns=None, angle_rows={}, debate_run={
            "status": "ok",
            "tasks": [{"agent_name": "risk_officer", "result": "Leaning bullish, modest conviction."}],
        })
        signal = await fetch_debate_signal(tools, "AAPL", "long")
        assert signal.strength == pytest.approx(0.4)

    async def test_weight_multiplier_scales_strength(self) -> None:
        tools = _StubTools(returns=None, angle_rows={}, debate_run={
            "status": "ok",
            "tasks": [{"agent_name": "risk_officer", "result": "Bullish."}],
        })
        signal = await fetch_debate_signal(tools, "AAPL", "long", weight=1.5)
        assert signal.strength == pytest.approx(0.7 * 1.5)

    async def test_neutral_verdict_also_gets_conviction_tier(self) -> None:
        tools = _StubTools(returns=None, angle_rows={}, debate_run={
            "status": "ok",
            "tasks": [{"agent_name": "risk_officer", "result": "Neutral, high conviction no-trade call."}],
        })
        signal = await fetch_debate_signal(tools, "AAPL", "long")
        assert signal.direction == "neutral"
        assert signal.strength == pytest.approx(1.0)


def _contracts(near_expiration: str, far_expiration: str) -> list[dict]:
    return [
        {"expiration": near_expiration, "strike": 90.0, "type": "C", "implied_volatility": 0.20},
        {"expiration": near_expiration, "strike": 100.0, "type": "C", "implied_volatility": 0.25},
        {"expiration": near_expiration, "strike": 110.0, "type": "C", "implied_volatility": 0.30},
        {"expiration": near_expiration, "strike": 90.0, "type": "P", "implied_volatility": 0.35},
        {"expiration": near_expiration, "strike": 100.0, "type": "P", "implied_volatility": 0.40},
        {"expiration": near_expiration, "strike": 110.0, "type": "P", "implied_volatility": 0.45},
        # A further-out expiration present too -- must not be picked as "nearest".
        {"expiration": far_expiration, "strike": 100.0, "type": "C", "implied_volatility": 0.99},
    ]


class TestFetchOptionsContext:
    async def test_unavailable_when_no_snapshot(self) -> None:
        tools = _StubTools(returns=None, angle_rows={}, options_snapshot=None)
        ctx = await fetch_options_context(tools, "AAPL")
        assert ctx == {"status": "unavailable"}

    async def test_unavailable_when_status_not_ok(self) -> None:
        tools = _StubTools(returns=None, angle_rows={}, options_snapshot={"status": "empty", "contracts": []})
        ctx = await fetch_options_context(tools, "AAPL")
        assert ctx == {"status": "unavailable"}

    async def test_unavailable_when_no_usable_rows(self) -> None:
        tools = _StubTools(
            returns=None, angle_rows={},
            options_snapshot={"status": "ok", "contracts": [{"expiration": None, "strike": None, "implied_volatility": None}]},
        )
        ctx = await fetch_options_context(tools, "AAPL")
        assert ctx == {"status": "unavailable"}

    async def test_picks_nearest_expiration_and_median_strike_as_atm(self) -> None:
        from datetime import datetime, timedelta, timezone

        near = (datetime.now(timezone.utc).date() + timedelta(days=10)).isoformat()
        far = (datetime.now(timezone.utc).date() + timedelta(days=100)).isoformat()
        tools = _StubTools(
            returns=None, angle_rows={},
            options_snapshot={"status": "ok", "contracts": _contracts(near, far)},
        )
        ctx = await fetch_options_context(tools, "AAPL")
        assert ctx["status"] == "ok"
        assert ctx["nearest_expiration"] == near
        # Median strike (100) call IV is 0.25 -- confirms the far-expiration
        # 0.99 IV never leaks in.
        assert ctx["atm_iv"] == pytest.approx(0.25)
        assert ctx["days_to_nearest_expiry"] == pytest.approx(10, abs=1)

    async def test_iv_skew_is_avg_put_minus_avg_call(self) -> None:
        from datetime import datetime, timedelta, timezone

        near = (datetime.now(timezone.utc).date() + timedelta(days=5)).isoformat()
        contracts = [
            {"expiration": near, "strike": 90.0, "type": "C", "implied_volatility": 0.20},
            {"expiration": near, "strike": 100.0, "type": "C", "implied_volatility": 0.25},
            {"expiration": near, "strike": 110.0, "type": "C", "implied_volatility": 0.30},
            {"expiration": near, "strike": 90.0, "type": "P", "implied_volatility": 0.35},
            {"expiration": near, "strike": 100.0, "type": "P", "implied_volatility": 0.40},
            {"expiration": near, "strike": 110.0, "type": "P", "implied_volatility": 0.45},
        ]
        tools = _StubTools(
            returns=None, angle_rows={},
            options_snapshot={"status": "ok", "contracts": contracts},
        )
        ctx = await fetch_options_context(tools, "AAPL")
        # avg call IV = (0.20+0.25+0.30)/3 = 0.25; avg put IV = (0.35+0.40+0.45)/3 = 0.40
        assert ctx["iv_skew"] == pytest.approx(0.40 - 0.25)


class TestAuthorTradePlan:
    async def test_produces_complete_plan(self) -> None:
        tools = _StubTools(
            returns=_synthetic_returns(120),
            angle_rows={
                "shock_clustering": [{"cluster_members": [{"symbol": "MSFT", "shock_correlation": 0.75}]}],
            },
        )
        llm = _StubLlmClient({
            "direction": "long",
            "confidence": 0.65,
            "magnitude_pct": 0.03,
            "magnitude_std": 0.01,
            "horizon_days": 5,
            "reasoning": "personality gap-fill + positive drift",
        })
        plan = await author_trade_plan("aapl", "daily", ResearchConfig(), tools, llm)

        assert isinstance(plan, TradePlan)
        assert plan.symbol == "AAPL"
        assert plan.direction == "long"
        assert plan.forecast is not None
        assert plan.position_size_pct == plan.risk_bands.max_position_size_pct
        assert plan.risk_bands.var_95_limit >= 0
        # how-to-make-it-live.md #17: CVaR + daily vol frozen onto the plan so
        # the live entry path can gate/scale on them (they were computed by
        # fetch_risk_state but discarded by _build_risk_band before). Stored
        # as positive fractions; synthetic returns have real variance + losses.
        assert isinstance(plan.risk_bands.cvar_95_limit, float)
        assert isinstance(plan.risk_bands.daily_vol, float)
        assert plan.risk_bands.cvar_95_limit > 0
        assert plan.risk_bands.daily_vol > 0
        # Cluster membership present -> the cluster-correlation contingency rule fires.
        assert any(r.metric == "shock_cluster_correlation" for r in plan.contingency_rules)
        # Every rule is a mechanically evaluable metric/operator/threshold triple.
        for rule in plan.contingency_rules + plan.invalidation_conditions:
            assert rule.metric
            assert rule.operator in (">=", "<=", ">", "<", "==", "!=")
            assert isinstance(rule.threshold, float)

    async def test_no_cluster_rule_without_cluster_members(self) -> None:
        tools = _StubTools(returns=_synthetic_returns(120), angle_rows={})
        llm = _StubLlmClient({
            "direction": "neutral", "confidence": 0.0, "magnitude_pct": 0.0,
            "magnitude_std": 0.0, "horizon_days": 1,
        })
        plan = await author_trade_plan("AAPL", "daily", ResearchConfig(), tools, llm)
        assert not any(r.metric == "shock_cluster_correlation" for r in plan.contingency_rules)

    async def test_populates_checklists_signals_and_entry_decision(self) -> None:
        tools = _StubTools(
            returns=_synthetic_returns(120),
            angle_rows={
                "shock_clustering": [{"cluster_members": [{"symbol": "MSFT", "shock_correlation": 0.75}]}],
                "shock_personality": [{"gap_fill_rate": {"mean": 0.6}}],
            },
        )
        llm = _StubLlmClient({
            "direction": "long",
            "confidence": 0.7,
            "magnitude_pct": 0.03,
            "magnitude_std": 0.01,
            "horizon_days": 5,
            "reasoning": "personality gap-fill + positive drift",
        })
        plan = await author_trade_plan("aapl", "daily", ResearchConfig(), tools, llm)

        # entry_checklist/exit_checklist were declared on TradePlan but never
        # populated before this phase -- must be non-empty now.
        assert plan.entry_checklist
        assert all({"condition", "source"} <= set(row) for row in plan.entry_checklist)
        assert plan.exit_checklist
        assert all({"condition", "action", "source"} <= set(row) for row in plan.exit_checklist)
        # one exit_checklist row per invalidation condition, same source.
        assert len(plan.exit_checklist) == len(plan.invalidation_conditions)

        # Structured for/against signal ledger alongside the free-text reasoning.
        assert plan.forecast.signals
        assert plan.forecast.reasoning
        assert any(s.direction == "supporting" for s in plan.forecast.signals)
        assert any(s.direction == "contradicting" for s in plan.forecast.signals)
        for s in plan.forecast.signals:
            assert s.direction in ("supporting", "contradicting", "neutral")

    async def test_signal_ledger_includes_fetch_angle_signals(self) -> None:
        # Confirms fetch_angle_signals' output actually merges into the
        # authored plan's forecast.signals, not just the unit-tested
        # function in isolation.
        tools = _StubTools(
            returns=_synthetic_returns(120),
            angle_rows={
                "trend_lifecycle": [{"type": "lifecycle", "stage": "uptrend"}],
                "regime_analysis": [{"metric": "current_regime", "regime": "bull"}],
                "backtesting_44_metrics": [{"win_rate": 0.62, "profit_factor": 2.0}],
            },
        )
        llm = _StubLlmClient({
            "direction": "long", "confidence": 0.7, "magnitude_pct": 0.03,
            "magnitude_std": 0.01, "horizon_days": 5,
        })
        plan = await author_trade_plan("aapl", "daily", ResearchConfig(), tools, llm)

        signal_names = {s.signal for s in plan.forecast.signals}
        assert "trend_lifecycle_stage" in signal_names
        assert "current_regime_alignment" in signal_names
        assert "backtested_win_rate" in signal_names
        assert "backtested_profit_factor" in signal_names

        # Phase 3: entry_decision now also depends on the Trade Score tier
        # (regime_fit_score defaults to 0 with no market_state passed, which
        # caps the achievable score well below "strong" until Phase 4's
        # market-regime engine exists) -- so a confident forecast alone no
        # longer guarantees BUY. Assert the tier/decision relationship
        # itself, which _derive_entry_decision's own unit tests below pin
        # down precisely.
        assert plan.trade_score is not None
        if plan.trade_score.tier in ("watch", "no_trade"):
            assert plan.entry_decision == "WAIT"
        else:
            assert plan.entry_decision == "BUY"

    async def test_low_confidence_forces_wait_entry_decision(self) -> None:
        tools = _StubTools(returns=_synthetic_returns(120), angle_rows={})
        llm = _StubLlmClient({
            "direction": "long", "confidence": 0.2, "magnitude_pct": 0.01,
            "magnitude_std": 0.01, "horizon_days": 1,
        })
        plan = await author_trade_plan("AAPL", "daily", ResearchConfig(), tools, llm)
        assert plan.entry_decision == "WAIT"

    async def test_short_direction_maps_to_short_entry_decision(self) -> None:
        tools = _StubTools(returns=_synthetic_returns(120), angle_rows={})
        llm = _StubLlmClient({
            "direction": "short", "confidence": 0.8, "magnitude_pct": 0.02,
            "magnitude_std": 0.01, "horizon_days": 3,
        })
        plan = await author_trade_plan("AAPL", "daily", ResearchConfig(), tools, llm)
        assert plan.trade_score is not None
        if plan.trade_score.tier in ("watch", "no_trade"):
            assert plan.entry_decision == "WAIT"
        else:
            assert plan.entry_decision == "SHORT"

    async def test_strong_trade_score_produces_buy_not_wait(self) -> None:
        # Directly exercises _derive_entry_decision's tier branch (the
        # integration tests above can't reliably reach "strong"/"moderate"
        # since regime_fit_score is unreachable without Phase 4's
        # market-regime engine wired in yet).
        from vinu_research.trade_plan_authoring import _derive_entry_decision

        forecast = Forecast(direction="long", confidence=0.8, magnitude_pct=0.03)
        assert _derive_entry_decision(
            forecast, TradeScoreResult(total_score=115.0, tier="strong"),
        ) == "BUY"
        assert _derive_entry_decision(
            forecast, TradeScoreResult(total_score=95.0, tier="moderate"),
        ) == "BUY"
        assert _derive_entry_decision(
            forecast, TradeScoreResult(total_score=75.0, tier="watch"),
        ) == "WAIT"
        assert _derive_entry_decision(
            forecast, TradeScoreResult(total_score=50.0, tier="no_trade"),
        ) == "WAIT"

        short_forecast = Forecast(direction="short", confidence=0.8, magnitude_pct=0.02)
        assert _derive_entry_decision(
            short_forecast, TradeScoreResult(total_score=115.0, tier="strong"),
        ) == "SHORT"

    async def test_extra_checklist_entries_merge_into_plan(self) -> None:
        tools = _StubTools(returns=_synthetic_returns(120), angle_rows={})
        llm = _StubLlmClient({
            "direction": "long", "confidence": 0.7, "magnitude_pct": 0.02,
            "magnitude_std": 0.01, "horizon_days": 3,
        })
        extra = {
            "entry_rules": [{"condition": "adequate_liquidity", "status": "met", "source": "stock-price"}],
            "exit_rules": [{"condition": "trend_reversal", "action": "exit", "source": "trend_lifecycle"}],
        }
        plan = await author_trade_plan(
            "AAPL", "daily", ResearchConfig(), tools, llm, extra_checklist_entries=extra,
        )
        assert {"condition": "adequate_liquidity", "status": "met", "source": "stock-price"} in plan.entry_checklist
        assert {"condition": "trend_reversal", "action": "exit", "source": "trend_lifecycle"} in plan.exit_checklist


class TestTradePlanRoundTrip:
    """Phase 1 schema extension: expected_drawdown, signals, entry_decision,
    trade_score must all survive TradePlan.to_json()/from_json(), and old
    plans without them must still deserialize (safe defaults)."""

    def _sample_plan(self, **overrides) -> TradePlan:
        base = dict(
            symbol="AAPL",
            timeframe="daily",
            direction="long",
            entry_decision="BUY",
            forecast=Forecast(
                direction="long",
                confidence=0.6,
                magnitude_pct=0.02,
                signals=[
                    SignalEntry(signal="momentum", direction="supporting", strength=0.7, source="trend_lifecycle"),
                    SignalEntry(signal="resistance_nearby", direction="contradicting", strength=0.3, source="regime_analysis"),
                ],
            ),
            trade_score=TradeScoreResult(
                total_score=112.0, tier="strong", confluence_score=35.0,
                ev_score=30.0, risk_score=27.0, regime_fit_score=20.0,
                reasons=["strong confluence"],
            ),
        )
        base["risk_bands"] = RiskBand(expected_drawdown=0.04)
        base.update(overrides)
        return TradePlan(**base)

    def test_round_trip_preserves_new_fields(self) -> None:
        plan = self._sample_plan()
        round_tripped = TradePlan.from_json(plan.to_json())

        assert round_tripped.entry_decision == "BUY"
        assert round_tripped.risk_bands.expected_drawdown == 0.04
        assert [s.direction for s in round_tripped.forecast.signals] == ["supporting", "contradicting"]
        assert round_tripped.forecast.signals[0].signal == "momentum"
        assert round_tripped.trade_score.tier == "strong"
        assert round_tripped.trade_score.total_score == 112.0

    def test_round_trip_with_no_trade_score_or_signals(self) -> None:
        plan = TradePlan(symbol="AAPL", timeframe="daily", direction="long")
        round_tripped = TradePlan.from_json(plan.to_json())

        assert round_tripped.trade_score is None
        assert round_tripped.entry_decision == ""
        assert round_tripped.risk_bands.expected_drawdown == 0.0
        assert round_tripped.forecast is None

    def test_pre_phase1_json_without_new_fields_still_deserializes(self) -> None:
        # Simulates a TradePlan frozen before this phase existed -- no
        # entry_decision/trade_score/expected_drawdown/signals keys at all.
        import json

        legacy = json.dumps({
            "symbol": "AAPL",
            "timeframe": "daily",
            "direction": "long",
            "position_size_pct": 0.05,
            "risk_bands": {"max_position_size_pct": 0.05, "cvar_95_limit": 0.02},
            "tranches": [],
            "contingency_rules": [],
            "invalidation_conditions": [
                {"metric": "unrealized_pnl_pct", "operator": "<=", "threshold": -0.08, "action": "exit"},
            ],
            "forecast": {"direction": "long", "confidence": 0.6, "magnitude_pct": 0.02},
            "entry_checklist": [],
            "exit_checklist": [],
            "created_at": "2024-01-01T00:00:00+00:00",
            "version": 1,
        })
        plan = TradePlan.from_json(legacy)
        assert plan.symbol == "AAPL"
        assert plan.entry_decision == ""
        assert plan.trade_score is None
        assert plan.risk_bands.expected_drawdown == 0.0
        assert plan.forecast.signals == []


class TestFreezeAndApprove:
    def _sample_plan(self) -> TradePlan:
        return TradePlan(
            symbol="AAPL",
            timeframe="daily",
            direction="long",
            position_size_pct=0.05,
            forecast=Forecast(direction="long", confidence=0.6, magnitude_pct=0.02),
            # Stage A (A9): freeze_trade_plan now refuses a plan with no
            # invalidation conditions -- a real authored plan always has
            # some (see _build_invalidation_conditions), so the test helper
            # carries one too.
            invalidation_conditions=[
                InvalidationCondition(
                    metric="unrealized_pnl_pct", operator="<=", threshold=-0.08, action="exit",
                ),
            ],
        )

    def test_freeze_persists_as_created(self, strategy_store) -> None:
        artifact = freeze_trade_plan(strategy_store, self._sample_plan())
        assert artifact.type == "trade_plan"
        assert artifact.status == ArtifactStatus.CREATED
        assert artifact.trade_plan_data

        reloaded = strategy_store.get_artifact(artifact.artifact_id)
        assert reloaded is not None
        round_tripped = TradePlan.from_json(reloaded.trade_plan_data)
        assert round_tripped.symbol == "AAPL"
        assert round_tripped.forecast.direction == "long"

    def test_freeze_refuses_a_plan_with_no_invalidation_conditions(self, strategy_store) -> None:
        # Stage A (A9): a plan that can never be proven wrong must not be
        # frozen -- vinu-live would hold it open on the time-stop alone.
        plan = self._sample_plan()
        plan.invalidation_conditions = []
        with pytest.raises(ValueError, match="invalidation"):
            freeze_trade_plan(strategy_store, plan)

    def test_approve_fails_closed_with_no_calibration_and_no_active_strategy(self, strategy_store) -> None:
        # No calibration entries (none exist for a fresh plan -- see the
        # bootstrap test below) AND no ACTIVE strategy artifact for AAPL to
        # bootstrap from -- genuinely nothing to approve on.
        artifact = freeze_trade_plan(strategy_store, self._sample_plan())
        with pytest.raises(TradePlanApprovalError) as exc_info:
            approve_trade_plan(strategy_store, artifact.artifact_id)
        assert exc_info.value.reasons

    def test_approve_bootstraps_from_active_strategy_with_no_calibration_history(self, strategy_store) -> None:
        # Stage 0 (G2a bootstrap fix): calibration_entries can never exist
        # for a brand-new trade plan (they're only written after a position
        # closes, which requires the plan to already be ACTIVE) -- so the
        # gate must not simply fail closed forever. An ACTIVE strategy
        # artifact for the same symbol (which already cleared
        # meets_promotion_bar()) is sufficient to approve the plan's first
        # ever activation.
        from vinu_research.models import Artifact

        strategy = Artifact.create("strategy", "AAPL-strategy", universe=["AAPL"])
        strategy.status = ArtifactStatus.ACTIVE
        strategy_store.upsert_artifact(strategy)

        artifact = freeze_trade_plan(strategy_store, self._sample_plan())
        approved = approve_trade_plan(strategy_store, artifact.artifact_id)

        assert approved.status == ArtifactStatus.ACTIVE

    def test_approve_bootstrap_ignores_strategy_for_a_different_symbol(self, strategy_store) -> None:
        from vinu_research.models import Artifact

        strategy = Artifact.create("strategy", "MSFT-strategy", universe=["MSFT"])
        strategy.status = ArtifactStatus.ACTIVE
        strategy_store.upsert_artifact(strategy)

        artifact = freeze_trade_plan(strategy_store, self._sample_plan())  # AAPL plan
        with pytest.raises(TradePlanApprovalError):
            approve_trade_plan(strategy_store, artifact.artifact_id)

    def test_approve_succeeds_when_calibration_passes(self, strategy_store) -> None:
        artifact = freeze_trade_plan(strategy_store, self._sample_plan())
        cfg = ForecastSkillConfig(min_calibration_window=5)
        for _ in range(5):
            record_realized_outcome(strategy_store, artifact.artifact_id, 0.03, cfg)

        approved = approve_trade_plan(strategy_store, artifact.artifact_id, cfg)
        assert approved.status == ArtifactStatus.ACTIVE

    def test_approve_rejects_mutation_once_active(self, strategy_store) -> None:
        artifact = freeze_trade_plan(strategy_store, self._sample_plan())
        cfg = ForecastSkillConfig(min_calibration_window=5)
        for _ in range(5):
            record_realized_outcome(strategy_store, artifact.artifact_id, 0.03, cfg)
        approve_trade_plan(strategy_store, artifact.artifact_id, cfg)

        with pytest.raises(TradePlanApprovalError):
            approve_trade_plan(strategy_store, artifact.artifact_id, cfg)

    def test_approve_raises_for_missing_artifact(self, strategy_store) -> None:
        with pytest.raises(ValueError):
            approve_trade_plan(strategy_store, "does_not_exist")

    def test_force_approves_despite_no_active_strategy(self, strategy_store) -> None:
        # Stage 0 (G2b): a human override via Telegram/Discord's /approve_plan
        # command bypasses the bootstrap check, same "human accountability,
        # not a silent bypass" posture as /artifacts/{id}/promote?force=true.
        artifact = freeze_trade_plan(strategy_store, self._sample_plan())
        approved = approve_trade_plan(strategy_store, artifact.artifact_id, force=True, approver="alice")
        assert approved.status == ArtifactStatus.ACTIVE

    def test_force_approves_despite_failing_calibration(self, strategy_store) -> None:
        artifact = freeze_trade_plan(strategy_store, self._sample_plan())
        cfg = ForecastSkillConfig(min_calibration_window=5)
        for _ in range(5):
            record_realized_outcome(strategy_store, artifact.artifact_id, -0.05, cfg)  # losing streak

        approved = approve_trade_plan(strategy_store, artifact.artifact_id, cfg, force=True, approver="bob")
        assert approved.status == ArtifactStatus.ACTIVE

    def test_force_requires_an_approver(self, strategy_store) -> None:
        artifact = freeze_trade_plan(strategy_store, self._sample_plan())
        with pytest.raises(ValueError, match="approver"):
            approve_trade_plan(strategy_store, artifact.artifact_id, force=True)

    def test_force_still_rejects_mutation_once_active(self, strategy_store) -> None:
        # force overrides the calibration/bootstrap gate, not the
        # already-ACTIVE-is-immutable invariant -- that one is absolute.
        artifact = freeze_trade_plan(strategy_store, self._sample_plan())
        approve_trade_plan(strategy_store, artifact.artifact_id, force=True, approver="alice")

        with pytest.raises(TradePlanApprovalError):
            approve_trade_plan(strategy_store, artifact.artifact_id, force=True, approver="alice")

    def test_approve_rejects_no_trade_tier_even_with_active_strategy_bootstrap(self, strategy_store) -> None:
        # Phase 3: a "no_trade"-tier plan is refused at approval time even
        # when the bootstrap path (an ACTIVE strategy for the same symbol)
        # would otherwise have waved it through -- the Trade Score gate is a
        # separate, additional check, not folded into the calibration/
        # bootstrap logic above.
        strategy = Artifact.create(type_="strategy", name="s1", universe=["AAPL"])
        strategy.status = ArtifactStatus.ACTIVE
        strategy_store.upsert_artifact(strategy)

        plan = self._sample_plan()
        plan.trade_score = TradeScoreResult(total_score=50.0, tier="no_trade")
        artifact = freeze_trade_plan(strategy_store, plan)

        with pytest.raises(TradePlanApprovalError, match="no_trade"):
            approve_trade_plan(strategy_store, artifact.artifact_id)

    def test_approve_allows_watch_tier_to_pass_default_calibration_bootstrap(self, strategy_store) -> None:
        # min_tradeable_tier defaults to "watch" (TradeScoreThresholds), so a
        # watch-tier plan should NOT be blocked by the trade-score check --
        # only "no_trade" is below the default minimum.
        strategy = Artifact.create(type_="strategy", name="s1", universe=["AAPL"])
        strategy.status = ArtifactStatus.ACTIVE
        strategy_store.upsert_artifact(strategy)

        plan = self._sample_plan()
        plan.trade_score = TradeScoreResult(total_score=75.0, tier="watch")
        artifact = freeze_trade_plan(strategy_store, plan)

        approved = approve_trade_plan(strategy_store, artifact.artifact_id)
        assert approved.status == ArtifactStatus.ACTIVE

    def test_approval_recheck_uses_calibrated_thresholds_not_a_fresh_default(
        self, strategy_store, monkeypatch,
    ) -> None:
        """Regression: approve_trade_plan's tier re-check used to instantiate
        a fresh plain TradeScoreThresholds() instead of resolving the same
        calibrated thresholds author_trade_plan() itself uses -- harmless
        only while tier-cutoff calibration didn't exist yet. Here a
        calibrated threshold that requires "moderate" (raising the bar past
        the "watch" default) must actually be enforced at approval time."""
        import vinu_research.trade_plan_authoring as tpa
        from vinu_research.config import TradeScoreThresholds

        strategy = Artifact.create(type_="strategy", name="s1", universe=["AAPL"])
        strategy.status = ArtifactStatus.ACTIVE
        strategy_store.upsert_artifact(strategy)

        plan = self._sample_plan()
        plan.trade_score = TradeScoreResult(total_score=75.0, tier="watch")
        artifact = freeze_trade_plan(strategy_store, plan)

        monkeypatch.setattr(
            tpa, "load_active_thresholds",
            lambda: TradeScoreThresholds(min_tradeable_tier="moderate"),
        )

        with pytest.raises(TradePlanApprovalError, match="watch"):
            approve_trade_plan(strategy_store, artifact.artifact_id)

    def test_force_approves_despite_no_trade_tier(self, strategy_store) -> None:
        plan = self._sample_plan()
        plan.trade_score = TradeScoreResult(total_score=20.0, tier="no_trade")
        artifact = freeze_trade_plan(strategy_store, plan)

        approved = approve_trade_plan(strategy_store, artifact.artifact_id, force=True, approver="alice")
        assert approved.status == ArtifactStatus.ACTIVE

    def test_no_trade_score_on_plan_is_not_blocked(self, strategy_store) -> None:
        # A plan frozen before Phase 3 existed (trade_score=None) must not
        # be newly blocked by this check -- fail-open for old plans, same
        # contract as every other "never backfilled" field in this file.
        strategy = Artifact.create(type_="strategy", name="s1", universe=["AAPL"])
        strategy.status = ArtifactStatus.ACTIVE
        strategy_store.upsert_artifact(strategy)

        artifact = freeze_trade_plan(strategy_store, self._sample_plan())
        approved = approve_trade_plan(strategy_store, artifact.artifact_id)
        assert approved.status == ArtifactStatus.ACTIVE


class TestUpdateInTradeAction:
    """TradePlan.in_trade_action was defined on the schema since Phase 1 but
    nothing ever called a setter for it -- vinu-live's classify_action() only
    ever annotated an ephemeral per-cycle dict, never persisted back onto the
    artifact. update_in_trade_action closes that loop."""

    def _sample_plan(self) -> TradePlan:
        return TradePlan(
            symbol="AAPL", timeframe="daily", direction="long", position_size_pct=0.05,
            forecast=Forecast(direction="long", confidence=0.6, magnitude_pct=0.02),
            invalidation_conditions=[
                InvalidationCondition(
                    metric="unrealized_pnl_pct", operator="<=", threshold=-0.08, action="exit",
                ),
            ],
        )

    def test_persists_a_valid_action(self, strategy_store) -> None:
        artifact = freeze_trade_plan(strategy_store, self._sample_plan())

        updated = update_in_trade_action(strategy_store, artifact.artifact_id, "ADD")

        assert updated is not None
        reloaded = strategy_store.get_artifact(artifact.artifact_id)
        plan = TradePlan.from_json(reloaded.trade_plan_data)
        assert plan.in_trade_action == "ADD"

    def test_overwrites_a_previously_persisted_action(self, strategy_store) -> None:
        artifact = freeze_trade_plan(strategy_store, self._sample_plan())
        update_in_trade_action(strategy_store, artifact.artifact_id, "HOLD")

        update_in_trade_action(strategy_store, artifact.artifact_id, "REDUCE")

        reloaded = strategy_store.get_artifact(artifact.artifact_id)
        plan = TradePlan.from_json(reloaded.trade_plan_data)
        assert plan.in_trade_action == "REDUCE"

    def test_unrecognized_action_is_refused_not_persisted(self, strategy_store) -> None:
        artifact = freeze_trade_plan(strategy_store, self._sample_plan())

        result = update_in_trade_action(strategy_store, artifact.artifact_id, "SELL_EVERYTHING")

        assert result is None
        reloaded = strategy_store.get_artifact(artifact.artifact_id)
        plan = TradePlan.from_json(reloaded.trade_plan_data)
        assert plan.in_trade_action == ""

    def test_missing_artifact_fails_open(self, strategy_store) -> None:
        result = update_in_trade_action(strategy_store, "does_not_exist", "HOLD")
        assert result is None

    def test_artifact_with_no_trade_plan_data_fails_open(self, strategy_store) -> None:
        strategy = Artifact.create(type_="strategy", name="s1", universe=["AAPL"])
        strategy_store.upsert_artifact(strategy)

        result = update_in_trade_action(strategy_store, strategy.artifact_id, "HOLD")

        assert result is None


class TestRegimeAnalogueIntegration:
    """Phase 4's market-regime analogue is opt-in (config.regime_analogue_
    enabled, default False) -- author_trade_plan must not call it at all
    unless explicitly enabled, and must fail open (never raise) when it is
    enabled but the fetch/compute fails."""

    async def test_disabled_by_default_never_calls_regime_stats(self, monkeypatch) -> None:
        import vinu_research.trade_plan_authoring as tpa

        called = False

        async def _spy(*args, **kwargs):
            nonlocal called
            called = True
            return {}

        monkeypatch.setattr(tpa, "get_market_regime_stats_for_today", _spy)
        tools = _StubTools(returns=_synthetic_returns(120), angle_rows={})
        llm = _StubLlmClient({
            "direction": "long", "confidence": 0.7, "magnitude_pct": 0.02,
            "magnitude_std": 0.01, "horizon_days": 3,
        })
        await author_trade_plan("AAPL", "daily", ResearchConfig(), tools, llm)
        assert called is False

    async def test_enabled_feeds_regime_fit_score(self, monkeypatch) -> None:
        import vinu_research.trade_plan_authoring as tpa

        async def _fake_stats(*args, **kwargs):
            return {"positive_ratio": 0.9, "n_matches": 5}

        monkeypatch.setattr(tpa, "get_market_regime_stats_for_today", _fake_stats)
        tools = _StubTools(returns=_synthetic_returns(120), angle_rows={})
        llm = _StubLlmClient({
            "direction": "long", "confidence": 0.7, "magnitude_pct": 0.02,
            "magnitude_std": 0.01, "horizon_days": 3,
        })
        config = ResearchConfig(regime_analogue_enabled=True)
        plan = await author_trade_plan("AAPL", "daily", config, tools, llm)
        assert plan.trade_score is not None
        assert plan.trade_score.regime_fit_score > 0.0

    async def test_enabled_but_fetch_fails_still_produces_a_plan(self, monkeypatch) -> None:
        import vinu_research.trade_plan_authoring as tpa

        async def _raise(*args, **kwargs):
            raise RuntimeError("stock-price service down")

        monkeypatch.setattr(tpa, "get_market_regime_stats_for_today", _raise)
        tools = _StubTools(returns=_synthetic_returns(120), angle_rows={})
        llm = _StubLlmClient({
            "direction": "long", "confidence": 0.7, "magnitude_pct": 0.02,
            "magnitude_std": 0.01, "horizon_days": 3,
        })
        config = ResearchConfig(regime_analogue_enabled=True)
        plan = await author_trade_plan("AAPL", "daily", config, tools, llm)
        assert plan.trade_score is not None
        assert plan.trade_score.regime_fit_score == 0.0

    async def test_caller_supplied_market_state_is_not_mutated(self, monkeypatch) -> None:
        import vinu_research.trade_plan_authoring as tpa
        from vinu_research.market_state import MarketState

        async def _fake_stats(*args, **kwargs):
            return {"positive_ratio": 0.7}

        monkeypatch.setattr(tpa, "get_market_regime_stats_for_today", _fake_stats)
        tools = _StubTools(returns=_synthetic_returns(120), angle_rows={})
        llm = _StubLlmClient({
            "direction": "long", "confidence": 0.7, "magnitude_pct": 0.02,
            "magnitude_std": 0.01, "horizon_days": 3,
        })
        caller_state = MarketState(symbol="AAPL", liquidity={"normal": True})
        config = ResearchConfig(regime_analogue_enabled=True)
        await author_trade_plan("AAPL", "daily", config, tools, llm, market_state=caller_state)
        # author_trade_plan must merge into a copy, not the caller's object.
        assert caller_state.market_regime_stats == {}


class TestOptionsIvIntegration:
    """Phase 5's options-IV context is opt-in (config.options_iv_enabled,
    default False) -- author_trade_plan must not fetch it at all unless
    explicitly enabled, and a fetch failure must never break authoring."""

    def _options_snapshot(self) -> dict:
        from datetime import datetime, timedelta, timezone

        near = (datetime.now(timezone.utc).date() + timedelta(days=10)).isoformat()
        return {
            "status": "ok",
            "contracts": [
                {"expiration": near, "strike": 100.0, "type": "C", "implied_volatility": 0.30},
                {"expiration": near, "strike": 100.0, "type": "P", "implied_volatility": 0.35},
            ],
        }

    async def test_disabled_by_default_never_fetches_options(self) -> None:
        called = False

        class SpyTools(_StubTools):
            async def get_options_snapshot(self, symbol):
                nonlocal called
                called = True
                return self._options_snapshot_value

        tools = SpyTools(returns=_synthetic_returns(120), angle_rows={})
        tools._options_snapshot_value = self._options_snapshot()
        llm = _StubLlmClient({
            "direction": "long", "confidence": 0.7, "magnitude_pct": 0.02,
            "magnitude_std": 0.01, "horizon_days": 3,
        })
        await author_trade_plan("AAPL", "daily", ResearchConfig(), tools, llm)
        assert called is False

    async def test_enabled_blends_expected_drawdown_and_attaches_to_market_state(self) -> None:
        tools = _StubTools(
            returns=_synthetic_returns(120), angle_rows={}, options_snapshot=self._options_snapshot(),
        )
        llm = _StubLlmClient({
            "direction": "long", "confidence": 0.7, "magnitude_pct": 0.02,
            "magnitude_std": 0.01, "horizon_days": 3,
        })
        no_options_plan = await author_trade_plan(
            "AAPL", "daily", ResearchConfig(options_iv_enabled=False), tools, llm,
        )
        with_options_plan = await author_trade_plan(
            "AAPL", "daily", ResearchConfig(options_iv_enabled=True), tools, llm,
        )
        # Blending in a nonzero options-implied move must change the
        # GARCH-only expected_drawdown value.
        assert with_options_plan.risk_bands.expected_drawdown != no_options_plan.risk_bands.expected_drawdown

    async def test_enabled_but_fetch_fails_still_produces_a_plan(self) -> None:
        class RaisingTools(_StubTools):
            async def get_options_snapshot(self, symbol):
                raise RuntimeError("agent-api unreachable")

        tools = RaisingTools(returns=_synthetic_returns(120), angle_rows={})
        llm = _StubLlmClient({
            "direction": "long", "confidence": 0.7, "magnitude_pct": 0.02,
            "magnitude_std": 0.01, "horizon_days": 3,
        })
        config = ResearchConfig(options_iv_enabled=True)
        plan = await author_trade_plan("AAPL", "daily", config, tools, llm)
        assert plan is not None
        assert plan.forecast is not None

    async def test_no_options_data_available_leaves_plan_unaffected(self) -> None:
        tools = _StubTools(returns=_synthetic_returns(120), angle_rows={}, options_snapshot=None)
        llm = _StubLlmClient({
            "direction": "long", "confidence": 0.7, "magnitude_pct": 0.02,
            "magnitude_std": 0.01, "horizon_days": 3,
        })
        config = ResearchConfig(options_iv_enabled=True)
        plan = await author_trade_plan("AAPL", "daily", config, tools, llm)
        assert plan is not None


class TestTradeScorePositionSizing:
    """Verifies the position-size interaction called out in the plan as the
    highest-risk edit in this phase: compute_trade_score's tier scales
    RiskBand.max_position_size_pct on top of the existing half-Kelly calc.
    check_trade_score_gate is monkeypatched to pin the tier deterministically
    -- computing a real "strong"/"watch" tier from synthetic data would be
    brittle (it depends on regime_fit_score, unreachable without Phase 4).
    """

    async def _plan_with_tier(self, monkeypatch, tier: str, total_score: float) -> TradePlan:
        import vinu_research.trade_plan_authoring as tpa
        from vinu_research.gates.trade_score_gate import TradeScoreVerdict

        monkeypatch.setattr(
            tpa, "check_trade_score_gate",
            lambda *a, **k: TradeScoreVerdict(
                eligible=tier != "no_trade",
                result=TradeScoreResult(total_score=total_score, tier=tier),
            ),
        )
        tools = _StubTools(returns=_positive_edge_returns(), angle_rows={})
        llm = _StubLlmClient({
            "direction": "long", "confidence": 0.7, "magnitude_pct": 0.03,
            "magnitude_std": 0.01, "horizon_days": 5,
        })
        return await author_trade_plan("AAPL", "daily", ResearchConfig(), tools, llm)

    async def test_no_trade_tier_zeroes_position_size(self, monkeypatch) -> None:
        plan = await self._plan_with_tier(monkeypatch, "no_trade", 10.0)
        assert plan.risk_bands.max_position_size_pct == 0.0
        assert plan.position_size_pct == 0.0
        assert plan.entry_decision == "WAIT"

    async def test_watch_tier_scales_down_position_size(self, monkeypatch) -> None:
        unscaled_plan = await self._plan_with_tier(monkeypatch, "strong", 115.0)
        watch_plan = await self._plan_with_tier(monkeypatch, "watch", 75.0)
        # "watch" (0.4x) must size strictly smaller than "strong" (1.0x) for
        # the identical underlying risk_state/forecast.
        assert watch_plan.risk_bands.max_position_size_pct < unscaled_plan.risk_bands.max_position_size_pct
        assert watch_plan.entry_decision == "WAIT"

    async def test_strong_tier_keeps_full_size_and_allows_buy(self, monkeypatch) -> None:
        plan = await self._plan_with_tier(monkeypatch, "strong", 115.0)
        assert plan.entry_decision == "BUY"
        assert plan.risk_bands.max_position_size_pct > 0.0


class TestDebateSignalIntegration:
    """The investment_committee debate signal is opt-in (config.
    debate_signal_enabled, default False) -- author_trade_plan must not
    fetch it at all unless explicitly enabled, and a fetch failure must
    never break authoring."""

    async def test_disabled_by_default_never_fetches_debate(self) -> None:
        called = False

        class SpyTools(_StubTools):
            async def get_latest_debate_run(self, preset_name, symbol):
                nonlocal called
                called = True
                return {"status": "ok", "tasks": [{"agent_name": "risk_officer", "result": "bullish"}]}

        tools = SpyTools(returns=_synthetic_returns(120), angle_rows={})
        llm = _StubLlmClient({
            "direction": "long", "confidence": 0.7, "magnitude_pct": 0.02,
            "magnitude_std": 0.01, "horizon_days": 3,
        })
        plan = await author_trade_plan("AAPL", "daily", ResearchConfig(), tools, llm)

        assert called is False
        assert not any(s.signal == "investment_committee_debate" for s in plan.forecast.signals)

    async def test_enabled_feeds_debate_signal_into_ledger(self) -> None:
        tools = _StubTools(
            returns=_synthetic_returns(120), angle_rows={},
            debate_run={"status": "ok", "tasks": [{"agent_name": "risk_officer", "result": "bullish, high conviction"}]},
        )
        llm = _StubLlmClient({
            "direction": "long", "confidence": 0.7, "magnitude_pct": 0.02,
            "magnitude_std": 0.01, "horizon_days": 3,
        })
        config = ResearchConfig(debate_signal_enabled=True)

        plan = await author_trade_plan("AAPL", "daily", config, tools, llm)

        debate_signals = [s for s in plan.forecast.signals if s.signal == "investment_committee_debate"]
        assert len(debate_signals) == 1
        assert debate_signals[0].direction == "supporting"

    async def test_enabled_but_fetch_fails_still_produces_a_plan(self) -> None:
        class FailingTools(_StubTools):
            async def get_latest_debate_run(self, preset_name, symbol):
                raise ConnectionError("agent service down")

        tools = FailingTools(returns=_synthetic_returns(120), angle_rows={})
        llm = _StubLlmClient({
            "direction": "long", "confidence": 0.7, "magnitude_pct": 0.02,
            "magnitude_std": 0.01, "horizon_days": 3,
        })
        config = ResearchConfig(debate_signal_enabled=True)

        plan = await author_trade_plan("AAPL", "daily", config, tools, llm)

        assert plan is not None
        assert not any(s.signal == "investment_committee_debate" for s in plan.forecast.signals)

    async def test_debate_signal_weight_reaches_the_ledger(self) -> None:
        tools = _StubTools(
            returns=_synthetic_returns(120), angle_rows={},
            debate_run={"status": "ok", "tasks": [{"agent_name": "risk_officer", "result": "bullish"}]},
        )
        llm = _StubLlmClient({
            "direction": "long", "confidence": 0.7, "magnitude_pct": 0.02,
            "magnitude_std": 0.01, "horizon_days": 3,
        })
        config = ResearchConfig(debate_signal_enabled=True, debate_signal_weight=2.0)

        plan = await author_trade_plan("AAPL", "daily", config, tools, llm)

        debate_signals = [s for s in plan.forecast.signals if s.signal == "investment_committee_debate"]
        assert len(debate_signals) == 1
        assert debate_signals[0].strength == pytest.approx(0.7 * 2.0)


class TestRegimeRouterIntegration:
    """Regime router follow-up: current_regime tilts position size via
    config.regime_size_tilt_bound (default 0.3, on by default), a second
    channel independent of the existing confluence-score signal, and never
    breaks authoring when the regime fetch fails.

    check_trade_score_gate is monkeypatched to pin a "strong" tier, same
    reasoning TestTradeScorePositionSizing's own docstring gives -- a real
    tier from synthetic data is brittle and, at "no_trade", the tier's own
    0.0 size multiplier would swamp any regime tilt, making it invisible."""

    @staticmethod
    def _llm() -> "_StubLlmClient":
        return _StubLlmClient({
            "direction": "long", "confidence": 0.7, "magnitude_pct": 0.03,
            "magnitude_std": 0.01, "horizon_days": 3,
        })

    @staticmethod
    def _pin_strong_tier(monkeypatch) -> None:
        import vinu_research.trade_plan_authoring as tpa
        from vinu_research.gates.trade_score_gate import TradeScoreVerdict

        monkeypatch.setattr(
            tpa, "check_trade_score_gate",
            lambda *a, **k: TradeScoreVerdict(
                eligible=True, result=TradeScoreResult(total_score=115.0, tier="strong"),
            ),
        )

    async def test_favored_regime_sizes_larger_than_unfavored(self, monkeypatch) -> None:
        self._pin_strong_tier(monkeypatch)
        bull_tools = _StubTools(
            returns=_positive_edge_returns(), angle_rows={
                "regime_analysis": [{"metric": "current_regime", "regime": "bull"}],
            },
        )
        bear_tools = _StubTools(
            returns=_positive_edge_returns(), angle_rows={
                "regime_analysis": [{"metric": "current_regime", "regime": "bear"}],
            },
        )
        bull_plan = await author_trade_plan("AAPL", "daily", ResearchConfig(), bull_tools, self._llm())
        bear_plan = await author_trade_plan("AAPL", "daily", ResearchConfig(), bear_tools, self._llm())

        # Same forecast (long) in both -- bull favors it, bear penalizes it.
        assert bull_plan.risk_bands.max_position_size_pct > bear_plan.risk_bands.max_position_size_pct

    async def test_reasons_records_the_multiplier(self, monkeypatch) -> None:
        self._pin_strong_tier(monkeypatch)
        tools = _StubTools(
            returns=_positive_edge_returns(), angle_rows={
                "regime_analysis": [{"metric": "current_regime", "regime": "bull"}],
            },
        )
        plan = await author_trade_plan("AAPL", "daily", ResearchConfig(), tools, self._llm())

        assert any(r.startswith("regime_size_multiplier=") for r in plan.trade_score.reasons)
        assert any("regime=bull" in r for r in plan.trade_score.reasons)

    async def test_regime_fetch_failure_still_produces_a_plan(self, monkeypatch) -> None:
        self._pin_strong_tier(monkeypatch)

        class FailingTools(_StubTools):
            async def get_angle_rows(self, angle_name, symbol):
                if angle_name == "regime_analysis":
                    raise ConnectionError("angle service down")
                return await super().get_angle_rows(angle_name, symbol)

        tools = FailingTools(returns=_positive_edge_returns(), angle_rows={})
        plan = await author_trade_plan("AAPL", "daily", ResearchConfig(), tools, self._llm())

        assert plan is not None
        assert any("regime=unknown" in r for r in plan.trade_score.reasons)

    async def test_zero_bound_config_disables_the_tilt(self, monkeypatch) -> None:
        self._pin_strong_tier(monkeypatch)
        bull_tools = _StubTools(
            returns=_positive_edge_returns(), angle_rows={
                "regime_analysis": [{"metric": "current_regime", "regime": "bull"}],
            },
        )
        no_regime_tools = _StubTools(returns=_positive_edge_returns(), angle_rows={})
        config = ResearchConfig(regime_size_tilt_bound=0.0)

        bull_plan = await author_trade_plan("AAPL", "daily", config, bull_tools, self._llm())
        neutral_plan = await author_trade_plan("AAPL", "daily", config, no_regime_tools, self._llm())

        assert bull_plan.risk_bands.max_position_size_pct == pytest.approx(
            neutral_plan.risk_bands.max_position_size_pct
        )
