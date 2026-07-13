from vinu_strategy.engine.selection import run_selection, select_all, select_threshold, select_top_n


class TestSelection:
    def test_select_all(self):
        universe = ["AAPL", "MSFT", "GOOGL"]
        assert select_all(universe) == universe

    def test_select_threshold(self):
        signals = {"AAPL": 1.5, "MSFT": -0.5, "GOOGL": 0.0}
        result = select_threshold(signals, {"on": "signal", "min": 0.0})
        assert result == ["AAPL", "GOOGL"]

    def test_select_threshold_with_field(self):
        signals = {"AAPL": 0.0, "MSFT": 0.0, "GOOGL": 0.0}
        signal_context = {
            "AAPL": {"features": {"MOM_20": 1.5, "signal": 0.0}},
            "MSFT": {"features": {"MOM_20": -0.5, "signal": 0.0}},
            "GOOGL": {"features": {"MOM_20": 0.0, "signal": 0.0}},
        }
        result = select_threshold(signals, {"on": "MOM_20", "min": 0.0}, signal_context)
        assert result == ["AAPL", "GOOGL"]

    def test_select_threshold_with_field_fallback_no_context(self):
        signals = {"AAPL": 1.5, "MSFT": -0.5}
        result = select_threshold(signals, {"on": "MOM_20", "min": 0.0}, signal_context=None)
        assert result == ["AAPL"]

    def test_select_top_n(self):
        signals = {"AAPL": 3.0, "MSFT": 1.0, "GOOGL": 2.0}
        result = select_top_n(signals, {"n": 2})
        assert result == ["AAPL", "GOOGL"]

    def test_run_selection_all(self):
        universe = ["AAPL", "MSFT"]
        assert run_selection("all", universe) == universe

    def test_run_selection_unknown_fallback(self):
        universe = ["AAPL"]
        assert run_selection("unknown", universe) == universe
