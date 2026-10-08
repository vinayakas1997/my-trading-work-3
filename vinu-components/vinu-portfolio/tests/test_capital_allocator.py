from __future__ import annotations

import pytest

from vinu_portfolio.capital_allocator import (
    CapitalState,
    Candidate,
    allocate,
    kelly_position_fraction,
    shrunk_p_win,
)


def _cand(ticker="AAA", price=5.0, p_win=0.6, n=50, win=0.04, loss=0.02, cost=0.001, fractional=True):
    return Candidate(ticker=ticker, price=price, p_win=p_win, n_trades=n, avg_win=win, avg_loss=loss,
                     round_trip_cost=cost, fractional=fractional, artifact_id=f"art_{ticker}")


class TestCapitalState:
    def test_free_cash_is_real_capital_less_committed_less_reserve(self):
        s = CapitalState("real", 20.0, committed=1.76, reserve_fraction=0.4)
        assert s.reserve == pytest.approx(8.0) and s.free_cash == pytest.approx(10.24)

    def test_free_cash_is_never_negative(self):
        assert CapitalState("real", 20.0, committed=19.0, reserve_fraction=0.4).free_cash == 0.0

    def test_the_account_mode_tag_is_required_and_validated(self):
        with pytest.raises(ValueError):
            CapitalState("", 20.0)
        with pytest.raises(ValueError):
            CapitalState("live", 20.0)

    def test_the_paper_balance_is_not_the_base_unless_it_is_given_as_the_base(self):
        # the plan is computed from the capital it is handed: 20, not 96,613
        plan = allocate(CapitalState("real", 20.0), [_cand()])
        assert plan.real_capital == 20.0 and sum(f.amount for f in plan.funded) <= plan.free_cash_before + 1e-9


class TestAllocation:
    def test_nothing_is_allocated_above_the_free_cash(self):
        state = CapitalState("real", 20.0, committed=1.76)
        plan = allocate(state, [_cand("A"), _cand("B", p_win=0.7), _cand("C", p_win=0.65)], max_position_pct=1.0, kelly_scale=1.0)
        assert sum(f.amount for f in plan.funded) <= state.free_cash + 1e-9
        assert plan.free_cash_after >= -1e-9

    def test_the_committed_money_is_locked(self):
        a = allocate(CapitalState("real", 20.0, committed=0.0), [_cand()], max_position_pct=1.0, kelly_scale=1.0)
        b = allocate(CapitalState("real", 20.0, committed=1.76), [_cand()], max_position_pct=1.0, kelly_scale=1.0)
        assert b.free_cash_before == pytest.approx(a.free_cash_before - 1.76)

    def test_the_better_edge_is_funded_first(self):
        plan = allocate(CapitalState("real", 20.0), [_cand("LOW", p_win=0.52), _cand("HIGH", p_win=0.7)],
                        max_position_pct=1.0, kelly_scale=1.0)
        assert plan.funded[0].ticker == "HIGH"

    def test_no_edge_after_costs_is_refused(self):
        plan = allocate(CapitalState("real", 20.0), [_cand(p_win=0.4, cost=0.01)])
        assert not plan.funded and plan.refused[0]["reason"] == "no_edge_after_costs"

    def test_a_share_that_costs_more_than_the_free_cash_is_refused_when_not_fractional(self):
        plan = allocate(CapitalState("real", 20.0), [_cand(price=300.0, fractional=False)])
        assert not plan.funded and plan.refused[0]["reason"] == "price_above_available_funds"

    def test_a_fractional_ticker_can_be_bought_with_a_small_budget(self):
        plan = allocate(CapitalState("real", 20.0), [_cand(price=300.0, fractional=True)])
        assert plan.funded and 0 < plan.funded[0].shares < 1

    def test_the_fail_and_win_scenarios_are_reported(self):
        f = allocate(CapitalState("real", 20.0), [_cand()]).funded[0]
        assert f.cash_after_loss < f.cash_after_win

    def test_the_position_cap_binds(self):
        plan = allocate(CapitalState("real", 20.0, reserve_fraction=0.0), [_cand(p_win=0.9)], max_position_pct=0.1, kelly_scale=1.0)
        assert plan.funded[0].amount <= 20.0 * 0.1 + 1e-6

    def test_the_same_inputs_give_the_same_plan(self):
        s, c = CapitalState("real", 20.0), [_cand("A"), _cand("B", p_win=0.65)]
        assert allocate(s, c) == allocate(s, c)


class TestHonestWinRate:
    def test_few_trades_pull_the_rate_toward_half(self):
        assert shrunk_p_win(1.0, 5) < 0.7 and shrunk_p_win(1.0, 500) > 0.95

    def test_kelly_is_zero_or_less_without_an_edge(self):
        assert kelly_position_fraction(_cand(win=0.01, loss=0.02), 0.4) <= 0


class TestHeldMoney:
    def test_only_the_gap_to_the_target_is_funded(self):
        def plan(held):
            c = Candidate("AAA", None, 0.6, 50, 0.04, 0.02, 0.001, True, "a", held=held)
            return allocate(CapitalState("real", 20.0, committed=held), [c], max_position_pct=0.2, kelly_scale=1.0).funded[0]
        fresh, topped = plan(0.0), plan(1.0)
        assert topped.target_total == pytest.approx(fresh.target_total)
        assert topped.amount == pytest.approx(fresh.amount - 1.0)

    def test_a_position_already_at_its_target_is_kept_and_nothing_is_added(self):
        c = Candidate("AAA", None, 0.6, 50, 0.04, 0.02, 0.001, True, "a", held=5.0)
        f = allocate(CapitalState("real", 20.0, committed=5.0), [c], max_position_pct=0.1, kelly_scale=1.0).funded[0]
        assert f.amount == 0.0 and f.target_total == 5.0

    def test_the_free_cash_scale_shrinks_what_may_be_spent(self):
        full = allocate(CapitalState("real", 20.0), [_cand(price=None)], max_position_pct=1.0, kelly_scale=1.0)
        half = allocate(CapitalState("real", 20.0), [_cand(price=None)], max_position_pct=1.0, kelly_scale=1.0, free_cash_scale=0.5)
        assert half.free_cash_before == pytest.approx(full.free_cash_before / 2)
        assert sum(f.amount for f in half.funded) <= half.free_cash_before + 1e-9

    def test_an_unknown_price_skips_the_share_check(self):
        f = allocate(CapitalState("real", 20.0), [_cand(price=None)]).funded[0]
        assert f.shares is None and f.amount > 0
