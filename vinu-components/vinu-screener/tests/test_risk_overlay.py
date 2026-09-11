from __future__ import annotations

from vinu_screener.pipeline.risk_overlay import RiskCheck, RiskOverlayConfig, apply_risk_overlay


class TestDefaultChecks:
    def test_clean_candidate_has_no_penalty(self) -> None:
        result = apply_risk_overlay({"pe": 15.0, "pb": 3.0, "rsi": 50.0, "turnover": 0.05, "volume_ratio": 1.2})
        assert result.penalty == 0.0
        assert result.flags == []
        assert not result.vetoed

    def test_chase_momentum_flag(self) -> None:
        result = apply_risk_overlay({"chase_pct": 0.25})
        assert "chase_momentum" in result.flags
        assert result.penalty > 0

    def test_invalid_pe_flag(self) -> None:
        result = apply_risk_overlay({"pe": -5.0})
        assert "invalid_pe" in result.flags

    def test_stale_data_flag(self) -> None:
        result = apply_risk_overlay({"data_stale": True})
        assert "stale_data" in result.flags

    def test_multiple_flags_sum_penalty(self) -> None:
        result = apply_risk_overlay({"pe": -1.0, "pb": 20.0, "rsi": 90.0})
        assert set(result.flags) >= {"invalid_pe", "high_pb", "rsi_overbought"}
        assert result.penalty > 4.0  # more than any single check alone


class TestCappedAndVeto:
    def test_penalty_is_capped_at_max_penalty(self) -> None:
        cfg = RiskOverlayConfig(max_penalty=5.0)
        result = apply_risk_overlay({"pe": -1.0, "pb": 20.0, "rsi": 90.0, "turnover": 0.5}, cfg)
        assert result.penalty == 5.0

    def test_veto_penalty_threshold_vetoes_when_reached(self) -> None:
        cfg = RiskOverlayConfig(veto_penalty_threshold=10.0)
        result = apply_risk_overlay({"pe": -1.0, "pb": 20.0}, cfg)  # 4 + 4 = 8, below threshold
        assert not result.vetoed
        result2 = apply_risk_overlay({"pe": -1.0, "pb": 20.0, "rsi": 90.0}, cfg)  # 4+4+5=13 >= 10
        assert result2.vetoed

    def test_veto_high_risk_check_vetoes_when_enabled(self) -> None:
        checks = (RiskCheck("critical", lambda f: bool(f.get("critical")), penalty=1.0, veto=True),)
        cfg = RiskOverlayConfig(checks=checks, veto_high_risk=True)
        result = apply_risk_overlay({"critical": True}, cfg)
        assert result.vetoed
        assert "critical" in result.veto_reason

    def test_veto_check_without_veto_high_risk_flag_does_not_veto(self) -> None:
        checks = (RiskCheck("critical", lambda f: bool(f.get("critical")), penalty=1.0, veto=True),)
        cfg = RiskOverlayConfig(checks=checks, veto_high_risk=False)
        result = apply_risk_overlay({"critical": True}, cfg)
        assert not result.vetoed


class TestMalformedFields:
    def test_bad_predicate_input_is_skipped_not_raised(self) -> None:
        checks = (RiskCheck("boom", lambda f: 1 / 0 > 0, penalty=1.0),)  # noqa: B018
        cfg = RiskOverlayConfig(checks=checks)
        result = apply_risk_overlay({}, cfg)
        assert result.penalty == 0.0
        assert result.flags == []
