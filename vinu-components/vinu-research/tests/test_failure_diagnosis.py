"""The 'why did it fail' rules, checked against the numbers from the first real timeframe comparison (2026-10-04):
pullback setup, mean of 5 stocks, with the simulator's costs and with none."""

from __future__ import annotations

import pytest

from vinu_research.failure_diagnosis import Diagnosis, diagnose, diagnose_across, explain


def d(net_s, gross_s, net_r, gross_r, trades):
    return diagnose(net_sharpe=net_s, gross_sharpe=gross_s, net_return=net_r, gross_return=gross_r, trade_count=trades)


def test_15_minute_bars_have_no_edge_even_when_trading_is_free():
    x = d(-2.95, -0.49, -0.453, -0.118, 89)
    assert x.verdict == "no_edge" and not x.too_few_trades
    assert x.cost_drag_return == pytest.approx(0.335)          # -0.118 - (-0.453)
    assert "costs are not the cause" in explain(x)


def test_1_hour_bars_have_an_edge_that_costs_eat():
    x = d(-0.22, 0.34, -0.170, 0.207, 98)
    assert x.verdict == "edge_eaten_by_costs"
    assert x.cost_drag_return == pytest.approx(0.377)           # 0.207 - (-0.170)
    assert "costs removed 37.7%" in explain(x)


def test_4_hour_bars_survive_costs():
    x = d(0.25, 0.40, 0.271, 0.536, 59)
    assert x.verdict == "works_after_costs" and not x.too_few_trades


def test_daily_survives_costs_but_has_too_few_trades_to_trust():
    x = d(0.34, 0.39, 0.421, 0.493, 21)
    assert x.verdict == "works_after_costs" and x.too_few_trades
    assert "too few to judge" in explain(x)


@pytest.mark.parametrize("net,gross,verdict", [
    (0.05, 0.10, "no_edge"),                 # exactly at the floor counts as no edge
    (0.20, 0.30, "works_after_costs"),
    (0.10, 0.50, "edge_eaten_by_costs"),     # net exactly at the floor
])
def test_the_boundaries(net, gross, verdict):
    assert d(net, gross, 0.0, 0.0, 100).verdict == verdict


def test_across_tickers_consistent_when_most_agree():
    per = {s: d(-1, -0.5, -0.3, -0.1, 90) for s in ("A", "B", "C", "D")}
    per["E"] = d(0.4, 0.5, 0.2, 0.3, 90)
    r = diagnose_across(per)                                    # 4 of 5 = 0.8 agree
    assert r["consistency"] == "consistent" and r["majority"] == "no_edge"


def test_across_tickers_split_is_reported_as_ticker_specific():
    per = {"A": d(-1, -0.5, -0.3, -0.1, 90), "B": d(0.4, 0.5, 0.2, 0.3, 90), "C": d(0.4, 0.5, 0.2, 0.3, 90),
           "D": d(-0.2, 0.4, -0.1, 0.2, 90)}
    r = diagnose_across(per)
    assert r["consistency"] == "ticker_specific"
    assert r["verdicts"]["works_after_costs"] == ["B", "C"] and r["verdicts"]["no_edge"] == ["A"]


def test_empty_input_is_no_data_not_a_verdict():
    assert diagnose_across({})["consistency"] == "no_data"


def test_a_run_that_survives_costs_but_was_rejected_points_at_the_validation_tests():
    x = d(0.65, 0.74, 0.15, 0.18, 15)
    assert "validation tests" not in explain(x)                                  # on its own it says nothing about rejection
    text = explain(x, rejected_elsewhere=True)
    assert text.startswith("COSTS ARE NOT THE REASON IT WAS REJECTED")
    assert "rejected by the validation tests" in text and "only 15 trades" in text
