from __future__ import annotations

from vinu_screener.pipeline.hard_filter import HardFilterConfig, hard_filter_reasons, passes_hard_filter


class TestBounds:
    def test_empty_config_passes_everything(self) -> None:
        assert passes_hard_filter({}, HardFilterConfig())

    def test_min_price_bound(self) -> None:
        cfg = HardFilterConfig(min_price=10.0)
        assert not passes_hard_filter({"price": 5.0}, cfg)
        assert passes_hard_filter({"price": 15.0}, cfg)

    def test_max_price_bound(self) -> None:
        cfg = HardFilterConfig(max_price=100.0)
        assert not passes_hard_filter({"price": 150.0}, cfg)
        assert passes_hard_filter({"price": 50.0}, cfg)

    def test_pe_band(self) -> None:
        cfg = HardFilterConfig(pe_min=5.0, pe_max=30.0)
        assert passes_hard_filter({"pe": 20.0}, cfg)
        assert not passes_hard_filter({"pe": 3.0}, cfg)
        assert not passes_hard_filter({"pe": 40.0}, cfg)

    def test_signal_score_min(self) -> None:
        cfg = HardFilterConfig(signal_score_min=70.0)
        assert not passes_hard_filter({"signal_score": 60.0}, cfg)
        assert passes_hard_filter({"signal_score": 80.0}, cfg)


class TestFailClosed:
    def test_missing_field_fails_a_bound_that_needs_it(self) -> None:
        cfg = HardFilterConfig(min_price=1.0)
        assert not passes_hard_filter({}, cfg)

    def test_non_finite_field_fails(self) -> None:
        cfg = HardFilterConfig(min_price=1.0)
        assert not passes_hard_filter({"price": float("nan")}, cfg)
        assert not passes_hard_filter({"price": float("inf")}, cfg)

    def test_unset_bound_ignores_missing_field(self) -> None:
        # min_price is never set, so a missing "price" key must not fail it.
        cfg = HardFilterConfig(pe_min=1.0)
        assert passes_hard_filter({"pe": 5.0}, cfg)


class TestReasons:
    def test_reasons_list_names_the_failing_bound(self) -> None:
        cfg = HardFilterConfig(min_price=10.0, pe_max=20.0)
        reasons = hard_filter_reasons({"price": 5.0, "pe": 25.0}, cfg)
        assert len(reasons) == 2
        assert any("min_price" in r for r in reasons)
        assert any("pe_max" in r for r in reasons)

    def test_no_reasons_when_passing(self) -> None:
        cfg = HardFilterConfig(min_price=1.0)
        assert hard_filter_reasons({"price": 10.0}, cfg) == []
