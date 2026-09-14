from __future__ import annotations

from vinu_research.config import TradeScoreThresholds
from vinu_research.gates.trade_score_gate import (
    TIER_SIZE_MULTIPLIER,
    check_trade_score_gate,
    compute_trade_score,
)
from vinu_research.market_state import MarketState
from vinu_research.models import Forecast, RiskBand, SignalEntry


def _forecast(signals=None, confidence=0.6, magnitude_pct=0.02) -> Forecast:
    return Forecast(
        direction="long", confidence=confidence, magnitude_pct=magnitude_pct,
        signals=signals or [],
    )


class TestComputeTradeScore:
    def test_all_supporting_signals_maxes_confluence(self) -> None:
        forecast = _forecast(signals=[
            SignalEntry(signal="a", direction="supporting", strength=1.0),
            SignalEntry(signal="b", direction="supporting", strength=1.0),
        ])
        result = compute_trade_score(forecast, RiskBand(), None)
        assert result.confluence_score == TradeScoreThresholds().confluence_max

    def test_all_contradicting_signals_zeroes_confluence(self) -> None:
        forecast = _forecast(signals=[
            SignalEntry(signal="a", direction="contradicting", strength=1.0),
        ])
        result = compute_trade_score(forecast, RiskBand(), None)
        assert result.confluence_score == 0.0

    def test_no_signals_gives_neutral_half_confluence(self) -> None:
        forecast = _forecast(signals=[])
        result = compute_trade_score(forecast, RiskBand(), None)
        assert result.confluence_score == TradeScoreThresholds().confluence_max / 2.0

    def test_higher_expected_drawdown_lowers_risk_score(self) -> None:
        forecast = _forecast()
        low_dd = compute_trade_score(forecast, RiskBand(expected_drawdown=0.01), None)
        high_dd = compute_trade_score(forecast, RiskBand(expected_drawdown=0.08), None)
        assert low_dd.risk_score > high_dd.risk_score

    def test_no_risk_data_gives_neutral_half_risk_score(self) -> None:
        result = compute_trade_score(_forecast(), RiskBand(), None)
        assert result.risk_score == TradeScoreThresholds().risk_max / 2.0

    def test_regime_fit_defaults_to_zero_without_market_state(self) -> None:
        result = compute_trade_score(_forecast(), RiskBand(), None)
        assert result.regime_fit_score == 0.0

    def test_regime_fit_uses_market_state_positive_ratio(self) -> None:
        state = MarketState(symbol="AAPL", market_regime_stats={"positive_ratio": 0.8})
        result = compute_trade_score(_forecast(), RiskBand(), state)
        assert result.regime_fit_score == TradeScoreThresholds().regime_fit_max * 0.8

    def test_options_atm_iv_reduces_ev_score_as_extra_uncertainty_cost(self) -> None:
        # High-expectations spec #7: an options-implied IV should act as an
        # extra EV-reducing cost on top of the base cost_bps -- a high-IV
        # market_state must score strictly lower ev_score than an otherwise
        # identical low-IV one.
        low_iv_state = MarketState(symbol="AAPL", options={"status": "ok", "atm_iv": 0.10})
        high_iv_state = MarketState(symbol="AAPL", options={"status": "ok", "atm_iv": 0.80})
        forecast = _forecast(confidence=0.7, magnitude_pct=0.03)
        risk_band = RiskBand(expected_drawdown=0.02)
        low_iv_result = compute_trade_score(forecast, risk_band, low_iv_state)
        high_iv_result = compute_trade_score(forecast, risk_band, high_iv_state)
        assert high_iv_result.ev_score < low_iv_result.ev_score

    def test_missing_atm_iv_does_not_affect_ev_score(self) -> None:
        forecast = _forecast(confidence=0.7, magnitude_pct=0.03)
        risk_band = RiskBand(expected_drawdown=0.02)
        no_options = compute_trade_score(forecast, risk_band, None)
        empty_options_state = MarketState(symbol="AAPL", options={})
        with_empty_options = compute_trade_score(forecast, risk_band, empty_options_state)
        assert no_options.ev_score == with_empty_options.ev_score

    def test_total_score_is_sum_of_sub_scores(self) -> None:
        forecast = _forecast(signals=[SignalEntry(signal="a", direction="supporting", strength=1.0)])
        result = compute_trade_score(forecast, RiskBand(expected_drawdown=0.02), None)
        assert result.total_score == (
            result.confluence_score + result.ev_score + result.risk_score + result.regime_fit_score
        )

    def test_tier_boundaries(self) -> None:
        from vinu_research.gates.trade_score_gate import _tier_for

        config = TradeScoreThresholds()
        assert _tier_for(69.9, config) == "no_trade"
        assert _tier_for(70.0, config) == "watch"
        assert _tier_for(89.9, config) == "watch"
        assert _tier_for(90.0, config) == "moderate"
        assert _tier_for(110.0, config) == "moderate"
        assert _tier_for(110.1, config) == "strong"


class TestCheckTradeScoreGate:
    def test_fails_closed_below_min_tradeable_tier(self) -> None:
        forecast = _forecast(
            signals=[SignalEntry(signal="a", direction="contradicting", strength=1.0)],
            confidence=0.1, magnitude_pct=0.0,
        )
        verdict = check_trade_score_gate(forecast, RiskBand(expected_drawdown=0.15), None)
        assert verdict.result.tier == "no_trade"
        assert verdict.eligible is False
        assert any("below" in r for r in verdict.reasons)

    def test_passes_at_or_above_min_tradeable_tier(self) -> None:
        forecast = _forecast(
            signals=[
                SignalEntry(signal="a", direction="supporting", strength=1.0),
                SignalEntry(signal="b", direction="supporting", strength=1.0),
            ],
            confidence=0.8, magnitude_pct=0.03,
        )
        state = MarketState(symbol="AAPL", market_regime_stats={"positive_ratio": 0.9})
        verdict = check_trade_score_gate(forecast, RiskBand(expected_drawdown=0.005), state)
        assert verdict.eligible is True

    def test_custom_min_tradeable_tier(self) -> None:
        forecast = _forecast(signals=[SignalEntry(signal="a", direction="supporting", strength=0.5)])
        config = TradeScoreThresholds(min_tradeable_tier="strong")
        verdict = check_trade_score_gate(forecast, RiskBand(), None, config)
        assert verdict.result.tier != "strong"
        assert verdict.eligible is False


class TestRewardRiskVeto:
    def test_forces_no_trade_even_when_composite_would_be_strong(self) -> None:
        forecast = _forecast(
            signals=[
                SignalEntry(signal="a", direction="supporting", strength=1.0),
                SignalEntry(signal="b", direction="supporting", strength=1.0),
            ],
            confidence=0.9, magnitude_pct=0.03,
        )
        # expected_drawdown equal to magnitude_pct -> reward:risk == 1.0,
        # below the 1.5 default minimum -- despite every other sub-score
        # being maxed out (would otherwise score 126/135, well into "strong").
        risk_band = RiskBand(expected_drawdown=0.03, cvar_95_limit=0.03)
        state = MarketState(symbol="AAPL", market_regime_stats={"positive_ratio": 1.0})
        result = compute_trade_score(forecast, risk_band, state)
        assert result.total_score > TradeScoreThresholds().strong_threshold
        assert result.tier == "no_trade"
        assert any("reward:risk" in r for r in result.reasons)

    def test_veto_makes_gate_ineligible(self) -> None:
        forecast = _forecast(confidence=0.9, magnitude_pct=0.02)
        risk_band = RiskBand(expected_drawdown=0.02)
        verdict = check_trade_score_gate(forecast, risk_band, None)
        assert verdict.eligible is False
        assert verdict.result.tier == "no_trade"

    def test_good_reward_risk_is_not_vetoed(self) -> None:
        forecast = _forecast(confidence=0.9, magnitude_pct=0.03)
        risk_band = RiskBand(expected_drawdown=0.01)  # R:R = 3.0
        result = compute_trade_score(forecast, risk_band, None)
        assert not any("reward:risk" in r for r in result.reasons)

    def test_missing_expected_drawdown_fails_open_not_vetoed(self) -> None:
        # RiskBand() defaults expected_drawdown to 0.0 ("not computed") --
        # matches this module's fail-open convention for missing data
        # elsewhere (_confluence_score, _ev_score, _risk_score), rather than
        # treating an unknown denominator as an automatic veto.
        forecast = _forecast(confidence=0.9, magnitude_pct=0.03)
        result = compute_trade_score(forecast, RiskBand(), None)
        assert not any("reward:risk" in r for r in result.reasons)

    def test_custom_min_reward_risk_ratio(self) -> None:
        forecast = _forecast(confidence=0.9, magnitude_pct=0.03)
        risk_band = RiskBand(expected_drawdown=0.02)  # R:R = 1.5
        lenient = TradeScoreThresholds(min_reward_risk_ratio=1.0)
        strict = TradeScoreThresholds(min_reward_risk_ratio=2.0)
        assert not any(
            "reward:risk" in r for r in compute_trade_score(forecast, risk_band, None, lenient).reasons
        )
        assert any(
            "reward:risk" in r for r in compute_trade_score(forecast, risk_band, None, strict).reasons
        )


class TestTierSizeMultiplier:
    def test_covers_every_tier(self) -> None:
        for tier in ("strong", "moderate", "watch", "no_trade"):
            assert tier in TIER_SIZE_MULTIPLIER

    def test_no_trade_zeroes_out_sizing(self) -> None:
        assert TIER_SIZE_MULTIPLIER["no_trade"] == 0.0

    def test_strong_is_full_size(self) -> None:
        assert TIER_SIZE_MULTIPLIER["strong"] == 1.0
