"""Tests for `vinu-agent strategy-eval <ticker>` -- the read view over
strategy_evaluation_{history,status,step_registry}
(missing-pieces-of-system/startegy-enhancer/01-plan.md section 1, the
original "table where you can see what passed, what failed, and why"
ask this whole 3-table design exists to answer).
"""

from __future__ import annotations

import argparse

import pytest

from vinu_agent.cli import _cmd_strategy_eval, _parse_args


def _args(ticker: str, db: str = "") -> argparse.Namespace:
    return argparse.Namespace(ticker=ticker, db=db)


class TestParseArgs:
    def test_strategy_eval_parses_ticker(self) -> None:
        args = _parse_args(["strategy-eval", "AAPL"])
        assert args.command == "strategy-eval"
        assert args.ticker == "AAPL"
        assert args.db == ""

    def test_strategy_eval_accepts_db_override(self) -> None:
        args = _parse_args(["strategy-eval", "AAPL", "--db", "/tmp/x"])
        assert args.db == "/tmp/x"


class TestCmdStrategyEval:
    def test_no_data_root_configured(self, capsys, monkeypatch) -> None:
        monkeypatch.delenv("VINU_STRATEGY_EVAL_DATA_ROOT", raising=False)
        _cmd_strategy_eval(_args("AAPL"))
        out = capsys.readouterr().out
        assert "nothing to read" in out

    def test_no_history_for_ticker(self, capsys, tmp_path) -> None:
        from vinu_infra.strategy_evaluation import StrategyEvaluationStore

        StrategyEvaluationStore(tmp_path / "strategy_evaluation.db")  # schema only
        _cmd_strategy_eval(_args("AAPL", db=str(tmp_path)))
        out = capsys.readouterr().out
        assert "No real evaluation history for AAPL" in out

    def test_passed_candidate_shows_pass_with_no_rule_dump(self, capsys, tmp_path) -> None:
        from vinu_infra.strategy_evaluation import StrategyEvaluationStore

        store = StrategyEvaluationStore(tmp_path / "strategy_evaluation.db")
        store.write_step_result(
            artifact_id="art-1", ticker="AAPL", step_name="risk_critic",
            step_order=1, verdict="PASS", reasoning="final iteration critic_verdict=PASS",
        )

        _cmd_strategy_eval(_args("AAPL", db=str(tmp_path)))
        out = capsys.readouterr().out
        assert "art-1" in out
        assert "[PASS] risk_critic" in out
        assert "final iteration critic_verdict=PASS" in out
        # A PASS row should never print the general rule dump -- that's
        # only for FAIL, to explain the rejection.
        assert "rule:" not in out

    def test_failed_candidate_shows_reason_and_the_real_general_rule(self, capsys, tmp_path) -> None:
        from vinu_infra.strategy_evaluation import StrategyEvaluationStore, seed_step_registry

        store = StrategyEvaluationStore(tmp_path / "strategy_evaluation.db")
        seed_step_registry(store)
        store.write_step_result(
            artifact_id="art-1", ticker="AAPL", step_name="promotion_bar",
            step_order=2, verdict="FAIL",
            reasoning="deflated_sharpe 0.1 below threshold 0.3",
        )

        _cmd_strategy_eval(_args("AAPL", db=str(tmp_path)))
        out = capsys.readouterr().out
        assert "[FAIL] promotion_bar" in out
        assert "deflated_sharpe 0.1 below threshold 0.3" in out
        # The real, general rule from the step registry -- not just the
        # specific reason -- so a rejection is readable without code.
        assert "rule:" in out
        assert "deflated_sharpe >= config threshold" in out
        assert "source: vinu-research/vinu_research/promotion.py:30" in out

    def test_multiple_candidates_for_the_same_ticker_all_shown(self, capsys, tmp_path) -> None:
        from vinu_infra.strategy_evaluation import StrategyEvaluationStore

        store = StrategyEvaluationStore(tmp_path / "strategy_evaluation.db")
        store.write_step_result(
            artifact_id="art-1", ticker="AAPL", step_name="risk_critic",
            step_order=1, verdict="PASS",
        )
        store.write_step_result(
            artifact_id="art-2", ticker="AAPL", step_name="risk_critic",
            step_order=1, verdict="FAIL", reasoning="low trade count",
        )

        _cmd_strategy_eval(_args("AAPL", db=str(tmp_path)))
        out = capsys.readouterr().out
        assert "art-1" in out
        assert "art-2" in out

    def test_ticker_is_case_insensitive(self, capsys, tmp_path) -> None:
        from vinu_infra.strategy_evaluation import StrategyEvaluationStore

        store = StrategyEvaluationStore(tmp_path / "strategy_evaluation.db")
        store.write_step_result(
            artifact_id="art-1", ticker="AAPL", step_name="risk_critic",
            step_order=1, verdict="PASS",
        )

        _cmd_strategy_eval(_args("aapl", db=str(tmp_path)))
        out = capsys.readouterr().out
        assert "art-1" in out

    def test_only_the_failed_step_gets_a_rule_dump_not_the_whole_candidate(self, capsys, tmp_path) -> None:
        """A candidate that passed step 1 then failed step 2 should show
        the rule dump only under step 2's row, not step 1's."""
        from vinu_infra.strategy_evaluation import StrategyEvaluationStore, seed_step_registry

        store = StrategyEvaluationStore(tmp_path / "strategy_evaluation.db")
        seed_step_registry(store)
        store.write_step_result(
            artifact_id="art-1", ticker="AAPL", step_name="risk_critic",
            step_order=1, verdict="PASS", reasoning="critic_verdict=PASS",
        )
        store.write_step_result(
            artifact_id="art-1", ticker="AAPL", step_name="promotion_bar",
            step_order=2, verdict="FAIL", reasoning="deflated_sharpe too low",
        )

        _cmd_strategy_eval(_args("AAPL", db=str(tmp_path)))
        out = capsys.readouterr().out
        lines = out.splitlines()
        risk_critic_idx = next(i for i, l in enumerate(lines) if "risk_critic" in l)
        # The line right after risk_critic's own row must not be a rule
        # dump (it passed) -- it should go straight to the next step.
        assert "rule:" not in lines[risk_critic_idx + 1]
