from vinu_live.signal_translator import SignalTranslator


class TestSignalTranslator:
    def test_generates_buy_for_underweight_new_position(self) -> None:
        t = SignalTranslator()
        instrs = t.translate(
            target_weights=[{"symbol": "AAPL", "target_weight": 0.5, "name": "s1"}],
            current_positions={},
            portfolio_value=100_000.0,
            prices={"AAPL": 100.0},
        )
        assert len(instrs) == 1
        assert instrs[0].symbol == "AAPL"
        assert instrs[0].side == "buy"
        assert instrs[0].qty == 500.0

    def test_generates_sell_for_overweight_position(self) -> None:
        t = SignalTranslator()
        instrs = t.translate(
            target_weights=[{"symbol": "AAPL", "target_weight": 0.1, "name": "s1"}],
            current_positions={"AAPL": 500.0},
            portfolio_value=100_000.0,
            prices={"AAPL": 100.0},
        )
        assert len(instrs) == 1
        assert instrs[0].side == "sell"
        assert instrs[0].qty == 400.0

    def test_closes_position_dropped_from_target_weights(self) -> None:
        """The bug: a symbol held but no longer in target_weights (strategy
        exited it, or the strategy itself was dropped) must still generate a
        close instruction, not be silently left open forever."""
        t = SignalTranslator()
        instrs = t.translate(
            target_weights=[{"symbol": "MSFT", "target_weight": 0.5, "name": "s1"}],
            current_positions={"MSFT": 250.0, "AAPL": 100.0},
            portfolio_value=100_000.0,
            prices={"MSFT": 200.0, "AAPL": 100.0},
        )
        symbols = {i.symbol: i for i in instrs}
        assert "AAPL" in symbols
        assert symbols["AAPL"].side == "sell"
        assert symbols["AAPL"].qty == 100.0
        assert symbols["AAPL"].target_weight == 0.0

    def test_no_close_instruction_for_already_flat_position(self) -> None:
        t = SignalTranslator()
        instrs = t.translate(
            target_weights=[],
            current_positions={"AAPL": 0.0},
            portfolio_value=100_000.0,
            prices={"AAPL": 100.0},
        )
        assert instrs == []

    def test_zero_delta_is_omitted(self) -> None:
        t = SignalTranslator()
        instrs = t.translate(
            target_weights=[{"symbol": "AAPL", "target_weight": 0.5, "name": "s1"}],
            current_positions={"AAPL": 500.0},
            portfolio_value=100_000.0,
            prices={"AAPL": 100.0},
        )
        assert instrs == []
