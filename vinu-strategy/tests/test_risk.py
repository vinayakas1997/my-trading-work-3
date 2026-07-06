from vinu_strategy.engine.risk import run_risk


class TestRisk:
    def test_normalize(self):
        weights = {"AAPL": 10.0, "MSFT": 5.0}
        result = run_risk("normalize", weights, {"max_weight": 0.25, "cash_floor": 0.10})
        assert abs(result["AAPL"] - 0.25) < 0.001
        assert abs(result["MSFT"] - 0.25) < 0.001
        assert all(w <= 0.25 for w in result.values())

    def test_normalize_capped(self):
        weights = {"AAPL": 100.0}
        result = run_risk("normalize", weights, {"max_weight": 0.25})
        assert abs(result["AAPL"] - 0.25) < 0.001

    def test_normalize_empty(self):
        result = run_risk("normalize", {})
        assert result == {}

    def test_none_passthrough(self):
        weights = {"AAPL": 0.75, "MSFT": 0.25}
        result = run_risk("none", weights)
        assert result == weights

    def test_normalize_below_cap(self):
        weights = {"AAPL": 0.10, "MSFT": 0.05}
        result = run_risk("normalize", weights, {"max_weight": 0.25, "cash_floor": 0.10})
        assert abs(result["AAPL"] - 0.10) < 0.001
        assert abs(result["MSFT"] - 0.05) < 0.001

    def test_below_cap_no_scaling(self):
        weights = {"AAPL": 0.40, "MSFT": 0.30}
        result = run_risk("normalize", weights, {"max_weight": 0.50, "cash_floor": 0.10})
        assert abs(result["AAPL"] - 0.40) < 0.001
        assert abs(result["MSFT"] - 0.30) < 0.001

    def test_capped_above_cash_floor(self):
        weights = {"AAPL": 0.50, "MSFT": 0.50}
        result = run_risk("normalize", weights, {"max_weight": 0.50, "cash_floor": 0.10})
        assert abs(result["AAPL"] - 0.45) < 0.01
        assert abs(result["MSFT"] - 0.45) < 0.01

    def test_unknown_fallback(self):
        weights = {"AAPL": 0.15}
        result = run_risk("unknown", weights)
        assert abs(result["AAPL"] - 0.15) < 0.001

    def test_normalize_with_shorts(self):
        weights = {"AAPL": 0.167, "MSFT": -0.167}
        result = run_risk("normalize", weights, {"max_weight": 0.25, "cash_floor": 0.10})
        assert abs(result["AAPL"] - 0.167) < 0.001
        assert abs(result["MSFT"] + 0.167) < 0.001
        assert result["AAPL"] > 0
        assert result["MSFT"] < 0

    def test_normalize_with_shorts_capped(self):
        weights = {"AAPL": 0.50, "MSFT": -0.50}
        result = run_risk("normalize", weights, {"max_weight": 0.25, "cash_floor": 0.10})
        assert abs(result["AAPL"]) <= 0.25
        assert abs(result["MSFT"]) <= 0.25
        assert result["AAPL"] > 0
        assert result["MSFT"] < 0

    def test_normalize_with_shorts_scaled(self):
        weights = {"AAPL": 0.50, "MSFT": -0.50}
        result = run_risk("normalize", weights, {"max_weight": 0.50, "cash_floor": 0.10})
        assert abs(result["AAPL"] - 0.45) < 0.01
        assert abs(result["MSFT"] + 0.45) < 0.01
        assert result["AAPL"] > 0
        assert result["MSFT"] < 0

    def test_normalize_with_shorts_allow_short_false(self):
        weights = {"AAPL": 0.167, "MSFT": -0.167}
        result = run_risk("normalize", weights, {"max_weight": 0.25, "cash_floor": 0.10, "allow_short": False})
        assert result == {"AAPL": 0.167}

    def test_normalize_with_shorts_allow_short_false_all_short(self):
        weights = {"AAPL": -0.5, "MSFT": -0.5}
        result = run_risk("normalize", weights, {"max_weight": 0.25, "allow_short": False})
        assert result == {}

    def test_normalize_with_shorts_max_short_weight(self):
        weights = {"AAPL": -0.50}
        result = run_risk("normalize", weights, {"max_weight": 0.25, "max_short_weight": 0.10})
        assert abs(result["AAPL"] + 0.10) < 0.001
        assert result["AAPL"] < 0
