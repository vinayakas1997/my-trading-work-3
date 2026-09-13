import logging

from vinu_strategy.engine.allocation import run_allocation, allocate_equal, allocate_signal_scaled


class TestAllocation:
    def test_allocate_equal(self):
        candidates = ["AAPL", "MSFT", "GOOGL"]
        result = allocate_equal(candidates)
        assert abs(sum(result.values()) - 1.0) < 0.001
        assert all(abs(w - 1/3) < 0.001 for w in result.values())

    def test_equal_empty(self):
        assert allocate_equal([]) == {}

    def test_allocate_signal_scaled(self):
        candidates = ["AAPL", "MSFT"]
        signals = {"AAPL": 2.0, "MSFT": 1.0}
        result = allocate_signal_scaled(candidates, signals)
        assert abs(result["AAPL"] - 2/3) < 0.001
        assert abs(result["MSFT"] - 1/3) < 0.001

    def test_signal_scaled_zero_total(self):
        candidates = ["AAPL", "MSFT"]
        signals = {"AAPL": 0.0, "MSFT": 0.0}
        result = allocate_signal_scaled(candidates, signals)
        assert abs(sum(result.values()) - 1.0) < 0.001

    def test_signal_scaled_with_expression(self):
        candidates = ["AAPL", "MSFT"]
        signals = {"AAPL": 0.0, "MSFT": 0.0}
        signal_context = {
            "AAPL": {"features": {"SMA_9": 110.0, "SMA_21": 100.0}},
            "MSFT": {"features": {"SMA_9": 95.0, "SMA_21": 100.0}},
        }
        result = allocate_signal_scaled(
            candidates, signals,
            params={"signal": "SMA_9 / SMA_21 - 1"},
            signal_context=signal_context,
        )
        assert abs(abs(result["AAPL"]) - 2/3) < 0.01
        assert abs(abs(result["MSFT"]) - 1/3) < 0.01
        assert result["AAPL"] > 0
        assert result["MSFT"] < 0

    def test_signal_scaled_expression_empty_candidates(self):
        result = allocate_signal_scaled([], {}, params={"signal": "x + 1"}, signal_context={})
        assert result == {}

    def test_signal_scaled_expression_fallback_no_context(self):
        candidates = ["AAPL", "MSFT"]
        signals = {"AAPL": 2.0, "MSFT": 1.0}
        result = allocate_signal_scaled(candidates, signals, params={"signal": "SMA_9 / SMA_21 - 1"})
        assert abs(result["AAPL"] - 2/3) < 0.001
        assert abs(result["MSFT"] - 1/3) < 0.001

    def test_signal_scaled_with_rsi_mean_reversion(self):
        candidates = ["AAPL", "MSFT"]
        signals = {"AAPL": 0.0, "MSFT": 0.0}
        signal_context = {
            "AAPL": {"features": {"RSI_14": 25.0}},
            "MSFT": {"features": {"RSI_14": 75.0}},
        }
        expr = "max(0, (30 - RSI_14) / 30) - max(0, (RSI_14 - 70) / 30)"
        result = allocate_signal_scaled(
            candidates, signals,
            params={"signal": expr},
            signal_context=signal_context,
        )
        assert result["AAPL"] > 0
        assert result["MSFT"] < 0

    def test_signal_scaled_candidates_empty(self):
        assert allocate_signal_scaled([], {}, signal_context={}) == {}

    def test_expression_failure_for_every_candidate_logs_at_error_not_warning(self, caplog):
        """A typo'd field name in a strategy's expression makes every
        candidate's contribution silently 0 -> equal-weight fallback, which
        is indistinguishable downstream from a legitimate flat-signal day.
        That misconfiguration must be loud (ERROR), not blend in at WARNING."""
        candidates = ["AAPL", "MSFT"]
        signal_context = {
            "AAPL": {"features": {"MOM_20": 1.5}},
            "MSFT": {"features": {"MOM_20": -0.5}},
        }
        with caplog.at_level(logging.ERROR, logger="vinu_strategy.engine.allocation"):
            result = allocate_signal_scaled(
                candidates, {}, params={"signal": "made_up_field * 2"}, signal_context=signal_context,
            )
        assert abs(sum(result.values()) - 1.0) < 0.001
        assert any(
            r.levelno == logging.ERROR and "made_up_field" in r.message
            for r in caplog.records
        )

    def test_run_allocation_unknown(self):
        candidates = ["AAPL"]
        result = run_allocation("unknown", candidates)
        assert result == {"AAPL": 1.0}
