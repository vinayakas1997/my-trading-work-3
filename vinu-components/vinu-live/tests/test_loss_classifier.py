from vinu_live.trade_plan.loss_classifier import classify_exit_cause


class TestClassifyExitCause:
    def test_winning_trade_is_expected_outcome_regardless_of_rule(self) -> None:
        rule = {"metric": "drawdown_pct", "condition": "drawdown_pct >= 0.05"}
        assert classify_exit_cause(rule, realized_pnl=100.0) == "expected_outcome"

    def test_drawdown_pct_metric_is_risk_error(self) -> None:
        rule = {"metric": "drawdown_pct", "condition": "drawdown_pct >= 0.05"}
        assert classify_exit_cause(rule, realized_pnl=-50.0) == "risk_error"

    def test_realized_vol_ratio_metric_is_risk_error(self) -> None:
        rule = {"metric": "realized_vol_ratio", "condition": "realized_vol_ratio >= 2.0"}
        assert classify_exit_cause(rule, realized_pnl=-50.0) == "risk_error"

    def test_shock_cluster_correlation_metric_is_regime_change_error(self) -> None:
        rule = {"metric": "shock_cluster_correlation", "condition": "shock_cluster_correlation >= 0.8"}
        assert classify_exit_cause(rule, realized_pnl=-50.0) == "regime_change_error"

    def test_thesis_recheck_condition_is_prediction_error(self) -> None:
        rule = {"metric": "", "condition": "thesis_recheck: debate now contradicts"}
        assert classify_exit_cause(rule, realized_pnl=-50.0) == "prediction_error"

    def test_time_stop_condition_is_time_decay(self) -> None:
        rule = {"metric": "", "condition": "time_stop age 45d > max 30d"}
        assert classify_exit_cause(rule, realized_pnl=-50.0) == "time_decay"

    def test_unrecognized_rule_is_unclassified(self) -> None:
        rule = {"metric": "unrealized_pnl_pct", "condition": "unrealized_pnl_pct <= -0.10"}
        assert classify_exit_cause(rule, realized_pnl=-50.0) == "unclassified"

    def test_empty_rule_is_unclassified(self) -> None:
        assert classify_exit_cause({}, realized_pnl=-50.0) == "unclassified"

    def test_slippage_exceeded_adds_execution_error_tag(self) -> None:
        rule = {"metric": "drawdown_pct", "condition": "drawdown_pct >= 0.05"}
        result = classify_exit_cause(rule, realized_pnl=-50.0, slippage_exceeded=True)
        assert result == "risk_error+execution_error"

    def test_slippage_exceeded_on_a_win_stays_expected_outcome(self) -> None:
        rule = {"metric": "drawdown_pct", "condition": "drawdown_pct >= 0.05"}
        result = classify_exit_cause(rule, realized_pnl=100.0, slippage_exceeded=True)
        assert result == "expected_outcome"

    def test_slippage_exceeded_with_unclassified_rule(self) -> None:
        result = classify_exit_cause({}, realized_pnl=-50.0, slippage_exceeded=True)
        assert result == "unclassified+execution_error"
