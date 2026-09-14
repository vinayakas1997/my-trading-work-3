from __future__ import annotations

from vinu_strategy.service import StrategyService


def _reduce(angle_name: str, payload: dict) -> dict:
    # _reduce_angle doesn't touch `self`; testing it unbound avoids
    # constructing a full StrategyService (registry/storage/clients).
    return StrategyService._reduce_angle(None, angle_name, payload)


class TestReduceAngleRegimeAnalysis:
    def test_non_regime_angle_passed_through_unchanged(self) -> None:
        payload = {"data": [{"foo": "bar"}]}
        assert _reduce("news_sentiment", payload) == payload

    def test_prefers_current_regime_over_plurality_regime_stats(self) -> None:
        # The symbol has spent most of its history "sideways" (pct_of_time
        # 0.7) but is in "bull" right now -- the fixed behavior must report
        # the CURRENT regime, not the historically dominant one.
        payload = {
            "data": [
                {"metric": "regime_stats", "regime": "sideways", "pct_of_time": 0.7},
                {"metric": "regime_stats", "regime": "bull", "pct_of_time": 0.3},
                {"metric": "current_regime", "regime": "bull"},
            ]
        }
        result = _reduce("regime_analysis", payload)
        assert result["regime"] == "bull"

    def test_falls_back_to_plurality_regime_stats_when_no_current_regime_row(self) -> None:
        # Older, not-yet-reprocessed payloads may predate the current_regime
        # row -- fail open to the old behavior rather than losing the field.
        payload = {
            "data": [
                {"metric": "regime_stats", "regime": "sideways", "pct_of_time": 0.7},
                {"metric": "regime_stats", "regime": "bull", "pct_of_time": 0.3},
            ]
        }
        result = _reduce("regime_analysis", payload)
        assert result["regime"] == "sideways"

    def test_no_regime_rows_returns_payload_unchanged(self) -> None:
        payload = {"data": []}
        assert _reduce("regime_analysis", payload) == payload

    def test_preserves_other_payload_keys(self) -> None:
        payload = {
            "data": [{"metric": "current_regime", "regime": "bear"}],
            "status": "ok",
        }
        result = _reduce("regime_analysis", payload)
        assert result["regime"] == "bear"
        assert result["status"] == "ok"
