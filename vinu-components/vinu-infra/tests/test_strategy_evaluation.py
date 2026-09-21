"""Tests for vinu-infra/strategy_evaluation.py (missing-pieces-of-system/
startegy-enhancer/01-plan.md section 1)."""

from __future__ import annotations

from vinu_infra.strategy_evaluation import (
    STATUS_ACTIVE,
    STATUS_DECAYED,
    STATUS_IN_PROGRESS,
    STATUS_REJECTED,
    VERDICT_FAIL,
    VERDICT_PASS,
    StrategyEvaluationStore,
    seed_step_registry,
)


class TestWriteStepResultAndStatus:
    def test_single_pass_sets_in_progress(self, tmp_path):
        store = StrategyEvaluationStore(tmp_path / "se.db")
        store.write_step_result(
            artifact_id="art1", ticker="AAPL", step_name="risk_critic",
            step_order=1, verdict=VERDICT_PASS, reasoning="Sharpe 1.2, 40 trades",
        )
        status = store.get_status("art1")
        assert status is not None
        assert status["furthest_step_passed"] == 1
        assert status["status"] == STATUS_IN_PROGRESS
        assert status["rejected_at_step"] is None

    def test_fail_sets_rejected_with_reason(self, tmp_path):
        store = StrategyEvaluationStore(tmp_path / "se.db")
        store.write_step_result(
            artifact_id="art1", ticker="AAPL", step_name="risk_critic",
            step_order=1, verdict=VERDICT_PASS, reasoning="ok",
        )
        store.write_step_result(
            artifact_id="art1", ticker="AAPL", step_name="promotion_bar",
            step_order=2, verdict=VERDICT_FAIL,
            reasoning="deflated_sharpe 0.1 below threshold 0.3",
        )
        status = store.get_status("art1")
        assert status["status"] == STATUS_REJECTED
        assert status["rejected_at_step"] == "promotion_bar"
        assert "deflated_sharpe" in status["rejected_reason"]
        assert status["furthest_step_passed"] == 1

    def test_reaching_capital_allocator_sets_active(self, tmp_path):
        store = StrategyEvaluationStore(tmp_path / "se.db")
        for step_name, order in [
            ("risk_critic", 1), ("promotion_bar", 2), ("correlation_gate", 3),
            ("risk_gatekeeper", 4), ("capital_allocator", 5),
        ]:
            store.write_step_result(
                artifact_id="art1", ticker="AAPL", step_name=step_name,
                step_order=order, verdict=VERDICT_PASS,
            )
        status = store.get_status("art1")
        assert status["status"] == STATUS_ACTIVE
        assert status["furthest_step_passed"] == 5

    def test_decay_scan_fail_after_active_sets_decayed(self, tmp_path):
        store = StrategyEvaluationStore(tmp_path / "se.db")
        store.write_step_result(
            artifact_id="art1", ticker="AAPL", step_name="capital_allocator",
            step_order=5, verdict=VERDICT_PASS,
        )
        store.write_step_result(
            artifact_id="art1", ticker="AAPL", step_name="decay_scan",
            step_order=7, verdict=VERDICT_FAIL, reasoning="rolling Sharpe collapsed",
        )
        status = store.get_status("art1")
        assert status["status"] == STATUS_DECAYED
        assert status["rejected_at_step"] == "decay_scan"

    def test_history_records_every_attempt_in_order(self, tmp_path):
        store = StrategyEvaluationStore(tmp_path / "se.db")
        store.write_step_result(
            artifact_id="art1", ticker="AAPL", step_name="risk_critic",
            step_order=1, verdict=VERDICT_PASS,
        )
        store.write_step_result(
            artifact_id="art1", ticker="AAPL", step_name="promotion_bar",
            step_order=2, verdict=VERDICT_FAIL, reasoning="failed holdout",
        )
        history = store.get_history("art1")
        assert len(history) == 2
        assert history[0]["step_name"] == "risk_critic"
        assert history[1]["step_name"] == "promotion_bar"
        assert history[1]["reasoning"] == "failed holdout"

    def test_metrics_json_round_trips(self, tmp_path):
        store = StrategyEvaluationStore(tmp_path / "se.db")
        store.write_step_result(
            artifact_id="art1", ticker="AAPL", step_name="promotion_bar",
            step_order=2, verdict=VERDICT_FAIL, reasoning="below threshold",
            metrics={"deflated_sharpe": 0.1, "threshold": 0.3},
        )
        history = store.get_history("art1")
        import json
        metrics = json.loads(history[0]["metrics_json"])
        assert metrics["deflated_sharpe"] == 0.1

    def test_list_status_for_ticker_returns_multiple_candidates(self, tmp_path):
        store = StrategyEvaluationStore(tmp_path / "se.db")
        store.write_step_result(
            artifact_id="art1", ticker="AAPL", step_name="risk_critic",
            step_order=1, verdict=VERDICT_PASS,
        )
        store.write_step_result(
            artifact_id="art2", ticker="AAPL", step_name="risk_critic",
            step_order=1, verdict=VERDICT_FAIL, reasoning="low trade count",
        )
        results = store.list_status_for_ticker("aapl")
        assert {r["artifact_id"] for r in results} == {"art1", "art2"}

    def test_ticker_is_case_normalized(self, tmp_path):
        store = StrategyEvaluationStore(tmp_path / "se.db")
        store.write_step_result(
            artifact_id="art1", ticker="aapl", step_name="risk_critic",
            step_order=1, verdict=VERDICT_PASS,
        )
        assert store.get_status("art1")["ticker"] == "AAPL"


class TestStepRegistry:
    def test_seed_is_idempotent(self, tmp_path):
        store = StrategyEvaluationStore(tmp_path / "se.db")
        seed_step_registry(store)
        seed_step_registry(store)
        defs = store.list_step_definitions()
        assert len(defs) == 10
        names = [d["step_name"] for d in defs]
        assert len(names) == len(set(names))

    def test_seed_covers_all_10_real_steps(self, tmp_path):
        store = StrategyEvaluationStore(tmp_path / "se.db")
        seed_step_registry(store)
        names = {d["step_name"] for d in store.list_step_definitions()}
        assert names == {
            "risk_critic", "promotion_bar", "correlation_gate",
            "risk_gatekeeper", "capital_allocator", "shadow_evaluator",
            "decay_scan", "trade_score_gate", "approve_trade_plan",
            "order_guard",
        }

    def test_get_step_definition_returns_real_content(self, tmp_path):
        store = StrategyEvaluationStore(tmp_path / "se.db")
        seed_step_registry(store)
        defn = store.get_step_definition("promotion_bar")
        assert defn is not None
        assert "deflated_sharpe" in defn["pass_rule"]
        assert defn["source_file"] == "vinu-research/vinu_research/promotion.py:30"

    def test_ordered_by_step_order(self, tmp_path):
        store = StrategyEvaluationStore(tmp_path / "se.db")
        seed_step_registry(store)
        defs = store.list_step_definitions()
        orders = [d["step_order"] for d in defs]
        assert orders == sorted(orders)

    def test_missing_step_returns_none(self, tmp_path):
        store = StrategyEvaluationStore(tmp_path / "se.db")
        assert store.get_step_definition("not_a_real_step") is None
