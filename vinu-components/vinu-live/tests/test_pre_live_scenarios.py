"""Pre-live acceptance scenarios (2026-09-11): deterministic, engineered
OHLCV sequences with a KNOWN correct answer, driven through the REAL
`TradePlanOrchestrator` -- no LLM, no real network, no real broker. The
complement to `scripts/run_month_replay.py` (vinu-agent), which replays
real historical data through the real LLM agent and has no fixed
"correct" outcome to assert against; these scenarios exist specifically
so the mechanical pipeline -- entry, the catastrophic backstop, the
trailing-stop ratchet, and an invalidation exit -- can be proven correct
against a known answer before real capital is ever at risk, independent
of whatever an LLM happens to decide on a given day.

Re-verified before writing these (not guessed): the "trailing stop" the
orchestrator computes is BOOKKEEPING ONLY -- `update_stop_loss()`'s own
docstring says so, and `_evaluate_open_position` never compares price
against the ratcheted `stop_loss` to decide an exit. The actual exit
mechanism is two-layered by design (see orchestrator.py's own "Stage 0
(G3)" comment): (1) a static CVaR-sized catastrophic-backstop stop placed
as a REAL resting broker order at entry (protects the position even if
this process is down), and (2) invalidation_conditions/contingency_rules,
evaluated fresh every cycle against live P&L metrics -- the plan's actual,
dynamic exit logic. So "is the trailing stop taken care of properly"
splits into three separately-checkable claims, and that is exactly how
these three scenarios are split.

Reuses the exact same `book` fixture / `_make_orchestrator` / `_router` /
`_resp` helpers `test_trade_plan_orchestrator.py` already established --
these scenarios exercise the real `cycle()` / `_evaluate_open_position()`
code, not a reimplementation, same posture as every other test in this
suite.
"""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
from unittest.mock import AsyncMock

import pytest

from vinu_live.book.positions import init_book, list_open_positions, open_position
from vinu_live.config import LiveConfig
from vinu_live.trade_plan.orchestrator import TradePlanOrchestrator
from vinu_live.trade_plan.rebalance_intake import RebalanceRequestQueue

_ARTIFACT_ID = "art_prelive_1"


# Same small helpers test_trade_plan_orchestrator.py already established --
# duplicated locally rather than cross-file imported (pytest's rootdir/
# testpaths setup here doesn't add tests/ to sys.path the way a plain `cd
# tests && python -c "import ..."` does, so the cross-file import silently
# fails under the real `pytest tests/` invocation this repo actually uses).
@pytest.fixture
def book():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    be = init_book(db_path)
    yield be
    be.close()
    if os.path.exists(db_path):
        os.unlink(db_path)


def _make_orchestrator(book, **config_overrides) -> TradePlanOrchestrator:
    config = LiveConfig(**config_overrides)
    orch = TradePlanOrchestrator(config, book=book, rebalance_queue=RebalanceRequestQueue(":memory:"))
    orch._http = AsyncMock()
    return orch


def _resp(status_code=200, json_body=None):
    from unittest.mock import MagicMock

    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_body if json_body is not None else {}
    return resp


def _router(get_routes: dict, post_routes: dict | None = None):
    post_routes = post_routes or {}

    async def _get(url, params=None, **kwargs):
        for prefix, body in get_routes.items():
            if prefix in url:
                return _resp(json_body=body)
        return _resp(status_code=404)

    async def _post(url, json=None, **kwargs):
        for prefix, body in post_routes.items():
            if prefix in url:
                return _resp(json_body=body)
        return _resp(status_code=404)

    return AsyncMock(side_effect=_get), AsyncMock(side_effect=_post)


def _plan(**overrides) -> dict:
    plan = {
        "symbol": "AAPL",
        "timeframe": "daily",
        "direction": "long",
        "risk_bands": {"max_position_size_pct": 0.05},
        "contingency_rules": [],
        "invalidation_conditions": [],
        "forecast": {"direction": "long", "confidence": 0.6, "magnitude_pct": 0.03, "magnitude_std": 0.02},
    }
    plan.update(overrides)
    return plan


def _bars(closes: list[float]) -> dict:
    return {"data": [{"close": c} for c in closes]}


class TestScenarioEntryPlacesTheRealCatastrophicBackstop:
    """Known-correct answer: given a plan with a CVaR estimate and a fresh
    signal, one cycle() must (a) submit a real order sized off the plan's
    max_position_size_pct, (b) attach a resting stop at
    price*(1-cvar_95_limit) -- the "protected even if this process is
    down" backstop -- and (c) book the resulting open position with the
    correct entry price. This is the whole entry half of "complete
    workflow happening."
    """

    def test_entry_fires_with_correctly_sized_backstop(self, book) -> None:
        plan = _plan(risk_bands={"max_position_size_pct": 0.05, "cvar_95_limit": 0.05})
        orch = _make_orchestrator(book)
        get_mock, post_mock = _router(
            get_routes={
                "/research/artifacts": [{"artifact_id": _ARTIFACT_ID, "status": "ACTIVE", "type": "trade_plan"}],
                f"/research/trade-plan/{_ARTIFACT_ID}": {
                    "artifact_id": _ARTIFACT_ID, "trade_plan_data": json.dumps(plan),
                },
                "/candles/AAPL": _bars([100.0]),
                "/broker/account": {"configured": True, "equity": 100000.0},
                "/broker/positions": [],
            },
            post_routes={"/broker/order": {"status": "submitted", "order_id": "entry-1"}},
        )
        orch._http.get, orch._http.post = get_mock, post_mock

        result = asyncio.run(orch.cycle())

        assert result["actions"][0]["action"] == "entered"
        order_call = post_mock.await_args_list[0]
        assert order_call.kwargs["json"]["side"] == "buy"
        assert order_call.kwargs["json"]["stop_loss_price"] == 100.0 * (1 - 0.05)  # == 95.0

        open_positions = list_open_positions(book, symbol="AAPL")
        assert len(open_positions) == 1
        assert open_positions[0].avg_entry == 100.0
        assert open_positions[0].side == "long"

    def test_no_cvar_estimate_enters_without_a_backstop_price(self, book) -> None:
        """Fail-open by design (orchestrator.py's own comment): no invented
        stop distance when the plan carries no CVaR estimate -- a plain
        market order, same as the rest of this file's data-quality guards."""
        plan = _plan(risk_bands={"max_position_size_pct": 0.05})  # no cvar_95_limit
        orch = _make_orchestrator(book)
        get_mock, post_mock = _router(
            get_routes={
                "/research/artifacts": [{"artifact_id": _ARTIFACT_ID, "status": "ACTIVE", "type": "trade_plan"}],
                f"/research/trade-plan/{_ARTIFACT_ID}": {
                    "artifact_id": _ARTIFACT_ID, "trade_plan_data": json.dumps(plan),
                },
                "/candles/AAPL": _bars([100.0]),
                "/broker/account": {"configured": True, "equity": 100000.0},
                "/broker/positions": [],
            },
            post_routes={"/broker/order": {"status": "submitted", "order_id": "entry-2"}},
        )
        orch._http.get, orch._http.post = get_mock, post_mock

        result = asyncio.run(orch.cycle())

        assert result["actions"][0]["action"] == "entered"
        order_call = post_mock.await_args_list[0]
        assert order_call.kwargs["json"].get("stop_loss_price") is None


class TestScenarioTrailingStopRatchetsCorrectlyBarByBar:
    """Known-correct answer: on a clean rising sequence, the book's
    stop_loss field must (a) stay None until enough history exists,
    (b) then ratchet strictly upward as price rises, (c) always sit below
    the current price (a sane long stop), and (d) never loosen even on a
    flat/down bar within the sequence. Drives `_evaluate_open_position`
    bar by bar -- the same real trailing_stop_for() + ratchet-guard code
    `cycle()` calls internally, isolated from a full plan re-fetch each
    bar (existing test-suite convention)."""

    def test_stop_ratchets_up_and_never_loosens(self, book) -> None:
        open_position(book, "AAPL", "long", 10.0, 100.0)
        # Invalidation set unreachable on purpose -- this scenario isolates
        # the trailing ratchet from the exit-triggering scenario below.
        plan = _plan(invalidation_conditions=[
            {"metric": "unrealized_pnl_pct", "operator": "<=", "threshold": -0.90, "action": "exit", "action_params": {}},
        ])
        orch = _make_orchestrator(book)

        closes = [100.0, 101.0, 103.0, 102.5, 106.0, 110.0, 109.0, 115.0]
        seen_stops: list[float | None] = []
        for i in range(1, len(closes) + 1):
            window = closes[:i]
            get_mock, post_mock = _router(
                get_routes={"/candles/AAPL": _bars(window)},
                post_routes={"/broker/order": {"status": "submitted", "order_id": f"o{i}"}},
            )
            orch._http.get, orch._http.post = get_mock, post_mock
            position = list_open_positions(book, symbol="AAPL")[0]

            action = asyncio.run(orch._evaluate_open_position(plan, position, window[-1], 100000.0))

            # Found while writing this scenario, not assumed going in: once
            # the ratcheted stop implies a full 1R gain, a SEPARATE,
            # legitimate mechanism ("Bracket 50% at 1R") takes a partial
            # profit -- also correct behavior, not the invalidation exit
            # this scenario is isolating against. Either is a pass here.
            assert action["action"] in ("hold", "bracket_partial"), f"bar {i}: unexpected action {action}"
            seen_stops.append(list_open_positions(book, symbol="AAPL")[0].stop_loss)

        # Needs >= 3 closes -- the first two bars can't compute an ATR yet.
        assert seen_stops[0] is None
        assert seen_stops[1] is None
        populated = [s for s in seen_stops if s is not None]
        assert len(populated) >= 3

        # Ratchet-only: every populated value is >= the previous populated
        # value (never loosens), and strictly increases at least once
        # (the sequence trends up, so the stop must actually move).
        assert all(populated[i] >= populated[i - 1] for i in range(1, len(populated)))
        assert any(populated[i] > populated[i - 1] for i in range(1, len(populated)))

        # Sane long stop: always below the price it was computed against.
        for i, stop in enumerate(seen_stops):
            if stop is not None:
                assert stop < closes[i]


class TestScenarioInvalidationFiresTheRealExit:
    """Known-correct answer: an adverse move past the plan's own
    invalidation threshold must submit a real reduce_only exit order and
    close the book position -- the actual, dynamic exit mechanism
    (distinct from the bookkeeping-only trailing stop above)."""

    def test_adverse_move_past_threshold_exits_and_closes_the_book(self, book) -> None:
        open_position(book, "AAPL", "long", 10.0, 100.0)
        plan = _plan(invalidation_conditions=[
            {"metric": "unrealized_pnl_pct", "operator": "<=", "threshold": -0.08, "action": "exit", "action_params": {}},
        ])
        orch = _make_orchestrator(book)
        # -10% move -- past the -8% threshold. Broker confirms it actually
        # holds the matching AAPL position (scenario-06 fix: a 200-with-[]
        # response now means confirmed-flat, not "unreadable" -- this test
        # is about the invalidation threshold firing, not broker-flat
        # recovery, so it needs a broker view that matches the book).
        get_mock, post_mock = _router(
            get_routes={
                "/candles/AAPL": _bars([100.0, 98.0, 95.0, 90.0]),
                "/broker/positions": [{"symbol": "AAPL", "qty": 10.0}],
            },
            post_routes={"/broker/order": {"status": "submitted", "order_id": "exit-1"}},
        )
        orch._http.get, orch._http.post = get_mock, post_mock
        position = list_open_positions(book, symbol="AAPL")[0]

        action = asyncio.run(orch._evaluate_open_position(plan, position, 90.0, 100000.0))

        assert action["action"] == "invalidation_exit"
        order_call = post_mock.await_args_list[0]
        assert order_call.kwargs["json"]["side"] == "sell"
        assert order_call.kwargs["json"]["reduce_only"] is True
        assert list_open_positions(book, symbol="AAPL") == []

    def test_move_short_of_the_threshold_holds_instead(self, book) -> None:
        open_position(book, "AAPL", "long", 10.0, 100.0)
        plan = _plan(invalidation_conditions=[
            {"metric": "unrealized_pnl_pct", "operator": "<=", "threshold": -0.08, "action": "exit", "action_params": {}},
        ])
        orch = _make_orchestrator(book)
        # -5% move -- short of the -8% threshold, must NOT exit.
        get_mock, post_mock = _router(
            get_routes={"/candles/AAPL": _bars([100.0, 98.0, 96.0, 95.0])},
            post_routes={"/broker/order": {"status": "submitted", "order_id": "should-not-fire"}},
        )
        orch._http.get, orch._http.post = get_mock, post_mock
        position = list_open_positions(book, symbol="AAPL")[0]

        action = asyncio.run(orch._evaluate_open_position(plan, position, 95.0, 100000.0))

        assert action["action"] != "invalidation_exit"
        post_mock.assert_not_awaited()
        assert len(list_open_positions(book, symbol="AAPL")) == 1


class TestScenarioGapDownCrash:
    """the-reasoning-inefficiency/scenarios-test/01-gap-down-crash/
    scenario.md -- a realistic crash shape: one single bar gapping -25%,
    not a gradual multi-bar slide (the existing invalidation scenario
    above only ever tested a modest, gradual -10% move). Proves the
    invalidation check has no hidden assumption that a bad move arrives
    gradually over several bars, and that an unrealized-only loss (no
    realized daily loss yet) doesn't get spuriously blocked by the
    breaker's daily-loss check."""

    def test_single_bar_25pct_crash_exits_on_the_very_first_cycle_that_sees_it(self, book) -> None:
        open_position(book, "AAPL", "long", 10.0, 100.0)
        plan = _plan(invalidation_conditions=[
            {"metric": "unrealized_pnl_pct", "operator": "<=", "threshold": -0.08, "action": "exit", "action_params": {}},
        ])
        orch = _make_orchestrator(book)
        # A single gap-down bar straight to $75 (-25%) -- no gradual slide,
        # this is the only price data point the crash gives the system.
        # Broker view is genuinely unreachable here (a real transport
        # error, not a confirmed-flat 200-with-[] -- scenario-06's fix
        # made those two distinguishable) -- this test is specifically
        # about the no_broker_view fallback closing the full book qty.
        get_mock, post_mock = _router_with_errors(
            get_routes={"/candles/AAPL": _bars([100.0, 75.0])},
            get_errors={"/broker/positions"},
            post_routes={"/broker/order": {"status": "submitted", "order_id": "crash-exit-1"}},
            post_errors=set(),
        )
        orch._http.get, orch._http.post = get_mock, post_mock
        position = list_open_positions(book, symbol="AAPL")[0]

        action = asyncio.run(orch._evaluate_open_position(plan, position, 75.0, 100000.0))

        assert action["action"] == "invalidation_exit"
        order_call = post_mock.await_args_list[0]
        assert order_call.kwargs["json"]["side"] == "sell"
        assert order_call.kwargs["json"]["reduce_only"] is True
        assert order_call.kwargs["json"]["qty"] == pytest.approx(10.0)
        assert list_open_positions(book, symbol="AAPL") == []

    def test_no_realized_daily_loss_means_the_breaker_does_not_block_the_exit(self, book) -> None:
        open_position(book, "AAPL", "long", 10.0, 100.0)
        plan = _plan(invalidation_conditions=[
            {"metric": "unrealized_pnl_pct", "operator": "<=", "threshold": -0.08, "action": "exit", "action_params": {}},
        ])
        orch = _make_orchestrator(book)
        assert orch._breaker_state.halted is False  # fresh, nothing tripped it yet
        get_mock, post_mock = _router_with_errors(
            get_routes={"/candles/AAPL": _bars([100.0, 75.0])},
            get_errors={"/broker/positions"},
            post_routes={"/broker/order": {"status": "submitted", "order_id": "crash-exit-2"}},
            post_errors=set(),
        )
        orch._http.get, orch._http.post = get_mock, post_mock
        position = list_open_positions(book, symbol="AAPL")[0]

        action = asyncio.run(orch._evaluate_open_position(plan, position, 75.0, 100000.0))

        # Must be the real, filled exit -- not exit_blocked_by_breaker.
        assert action["action"] == "invalidation_exit"


class TestScenarioKillSwitchMidCycle:
    """the-reasoning-inefficiency/scenarios-test/02-kill-switch-mid-cycle/
    scenario.md -- proves the combination, not either half alone: within
    ONE real cycle() call with the kill switch reporting halted, a
    would-be entry (MSFT, no open position) is blocked while an existing
    open position's invalidation exit (AAPL) still fires. Existing tests
    already cover each half in isolation
    (test_halted_flag_blocks_new_entries,
    test_cycle_blocks_entry_when_agent_reports_halt in
    test_trade_plan_orchestrator.py) -- this is the first test proving
    they coexist correctly in the same cycle."""

    def test_entry_blocked_and_exit_still_fires_in_the_same_cycle(self, book) -> None:
        open_position(book, "AAPL", "long", 10.0, 100.0)
        aapl_plan = _plan(symbol="AAPL", invalidation_conditions=[
            {"metric": "unrealized_pnl_pct", "operator": "<=", "threshold": -0.08, "action": "exit", "action_params": {}},
        ])
        msft_plan = _plan(symbol="MSFT")
        orch = _make_orchestrator(book)
        get_mock, post_mock = _router(
            get_routes={
                "/research/artifacts": [
                    {"artifact_id": "art_aapl", "status": "ACTIVE", "type": "trade_plan"},
                    {"artifact_id": "art_msft", "status": "ACTIVE", "type": "trade_plan"},
                ],
                "/research/trade-plan/art_aapl": {"artifact_id": "art_aapl", "trade_plan_data": json.dumps(aapl_plan)},
                "/research/trade-plan/art_msft": {"artifact_id": "art_msft", "trade_plan_data": json.dumps(msft_plan)},
                # -10% on AAPL (past the -8% threshold); MSFT price is irrelevant
                # since the halt must block its entry before price even matters.
                "/candles/AAPL": _bars([100.0, 98.0, 95.0, 90.0]),
                "/candles/MSFT": _bars([50.0]),
                "/broker/account": {"configured": True, "equity": 100000.0},
                "/broker/status": {"halted": True},
                # Broker confirms it holds the matching AAPL position --
                # this scenario is about the halt not blocking the exit,
                # not about broker-flat recovery (scenario-06's fix made
                # a confirmed-flat 200-with-[] behave differently now).
                "/broker/positions": [{"symbol": "AAPL", "qty": 10.0}],
            },
            post_routes={"/broker/order": {"status": "submitted", "order_id": "kill-switch-exit-1"}},
        )
        orch._http.get, orch._http.post = get_mock, post_mock

        result = asyncio.run(orch.cycle())

        assert result["trading_halted"] is True
        actions_by_symbol = {a["symbol"]: a for a in result["actions"]}
        assert actions_by_symbol["MSFT"]["action"] == "entry_blocked_by_emergency_halt"
        assert actions_by_symbol["AAPL"]["action"] == "invalidation_exit"

        order_calls = [c for c in post_mock.await_args_list if "/broker/order" in c.args[0]]
        assert len(order_calls) == 1  # only AAPL's exit, never a MSFT entry
        assert order_calls[0].kwargs["json"]["symbol"] == "AAPL"
        assert order_calls[0].kwargs["json"]["reduce_only"] is True
        assert list_open_positions(book, symbol="AAPL") == []


class TestScenarioSidewaysChop:
    """the-reasoning-inefficiency/scenarios-test/03-sideways-chop/
    scenario.md -- entry is structurally unreachable once a position is
    open (_maybe_enter only ever runs when there's no open position), so
    the meaningful claim here isn't "no phantom entries" but "no phantom
    full exits / whipsaw on noise that never approaches the plan's real
    invalidation threshold." bracket_partial is accepted as a legitimate
    non-exit outcome (same as the original trailing-stop scenario) since
    whether the self-generated trailing stop's 1R gets crossed by this
    exact chop pattern depends on a computed ATR, not something to
    predict by reading the code."""

    def test_tight_chop_never_produces_a_spurious_full_exit(self, book) -> None:
        open_position(book, "AAPL", "long", 10.0, 100.0)
        plan = _plan(invalidation_conditions=[
            {"metric": "unrealized_pnl_pct", "operator": "<=", "threshold": -0.08, "action": "exit", "action_params": {}},
        ])
        orch = _make_orchestrator(book)

        # +/-2% chop, never approaching the -8% invalidation threshold.
        closes = [100.0, 102.0, 98.0, 101.0, 99.0, 102.0, 98.0, 101.0, 99.0, 102.0, 98.0, 101.0, 99.0]
        seen_actions: list[str] = []
        for i in range(1, len(closes) + 1):
            window = closes[:i]
            get_mock, post_mock = _router(
                get_routes={"/candles/AAPL": _bars(window)},
                post_routes={"/broker/order": {"status": "submitted", "order_id": f"chop-{i}"}},
            )
            orch._http.get, orch._http.post = get_mock, post_mock
            open_positions = list_open_positions(book, symbol="AAPL")
            assert open_positions, f"bar {i}: position closed early, chop should never fully exit it"
            position = open_positions[0]

            action = asyncio.run(orch._evaluate_open_position(plan, position, window[-1], 100000.0))
            seen_actions.append(action["action"])

            assert action["action"] not in (
                "invalidation_exit", "exit_not_filled", "exit_blocked_by_breaker",
                "rebalance_declined", "rebalance_honored", "rebalance_blocked_by_breaker",
            ), f"bar {i}: unexpected action {action} on tight chop that never crossed the threshold"

        assert list_open_positions(book, symbol="AAPL"), "chop must never fully close the position"
        assert set(seen_actions) <= {"hold", "bracket_partial"}


def _router_with_errors(get_routes: dict, get_errors: set[str], post_routes: dict, post_errors: set[str]):
    """Same shape as `_router`, but a prefix listed in `get_errors` /
    `post_errors` raises a transport error instead of returning a response --
    for scenarios that need to simulate the broker actually being
    unreachable, not just a flag being set."""

    async def _get(url, params=None, **kwargs):
        for prefix in get_errors:
            if prefix in url:
                raise ConnectionError(f"simulated broker outage: {prefix}")
        for prefix, body in get_routes.items():
            if prefix in url:
                return _resp(json_body=body)
        return _resp(status_code=404)

    async def _post(url, json=None, **kwargs):
        for prefix in post_errors:
            if prefix in url:
                raise ConnectionError(f"simulated broker outage: {prefix}")
        for prefix, body in post_routes.items():
            if prefix in url:
                return _resp(json_body=body)
        return _resp(status_code=404)

    return AsyncMock(side_effect=_get), AsyncMock(side_effect=_post)


class TestScenarioBrokerOutageMidCycle:
    """the-reasoning-inefficiency/scenarios-test/04-broker-outage-mid-cycle/
    scenario.md -- a materially different question from scenario 02's kill
    switch: a kill switch is a logical halt (the broker itself is still
    reachable, reduce_only is exempted downstream); a real broker outage
    means /agent/broker/order -- the exit's OWN order call -- is likely
    unreachable too, since it's the same connectivity. So the honest
    expectation here is NOT "the exit always fires despite the outage" --
    it's "the exit is still attempted, fails truthfully (exit_not_filled,
    not a false invalidation_exit), leaves the book position open, and
    correctly retries once the broker actually recovers." Existing test
    test_exit_never_gated_while_broker_degraded (test_trade_plan_orchestrator.py)
    already proves the flag itself doesn't gate the exit path, but with the
    order POST mocked to always succeed -- it doesn't cover what happens
    when the outage is real enough to also break the exit's own call."""

    def test_entry_paused_and_exit_fails_truthfully_then_recovers(self, book) -> None:
        open_position(book, "AAPL", "long", 10.0, 100.0)
        aapl_plan = _plan(symbol="AAPL", invalidation_conditions=[
            {"metric": "unrealized_pnl_pct", "operator": "<=", "threshold": -0.08, "action": "exit", "action_params": {}},
        ])
        msft_plan = _plan(symbol="MSFT")
        orch = _make_orchestrator(book)
        common_get_routes = {
            "/research/artifacts": [
                {"artifact_id": "art_aapl", "status": "ACTIVE", "type": "trade_plan"},
                {"artifact_id": "art_msft", "status": "ACTIVE", "type": "trade_plan"},
            ],
            "/research/trade-plan/art_aapl": {"artifact_id": "art_aapl", "trade_plan_data": json.dumps(aapl_plan)},
            "/research/trade-plan/art_msft": {"artifact_id": "art_msft", "trade_plan_data": json.dumps(msft_plan)},
            # -13.3% on AAPL (past the -8% threshold); MSFT price is irrelevant
            # since the outage must block its entry before price even matters.
            "/candles/AAPL": _bars([100.0, 98.0, 95.0, 87.0]),
            "/candles/MSFT": _bars([50.0]),
        }

        # Pass 1: full outage. /agent/broker/account (health probe),
        # /agent/broker/positions (reconciliation + _broker_close_plan), and
        # /agent/broker/order (the exit's own submit call) all unreachable --
        # a real outage, not just a degraded flag.
        get_mock, post_mock = _router_with_errors(
            get_routes=common_get_routes,
            get_errors={"/broker/account", "/broker/positions"},
            post_routes={},
            post_errors={"/broker/order"},
        )
        orch._http.get, orch._http.post = get_mock, post_mock

        result = asyncio.run(orch.cycle())

        assert result["status"] == "ok"  # no unhandled exception anywhere in the cycle
        assert result["broker_health"]["degraded"] is True
        assert orch._broker_degraded is True

        actions_by_symbol = {a["symbol"]: a for a in result["actions"]}
        assert actions_by_symbol["MSFT"]["action"] == "entry_blocked_by_broker_outage"
        assert actions_by_symbol["AAPL"]["action"] == "exit_not_filled"

        order_calls = [c for c in post_mock.await_args_list if "/broker/order" in c.args[0]]
        assert order_calls, "the exit must still be attempted -- _broker_degraded only gates entries"
        assert list_open_positions(book, symbol="AAPL"), "no confirmed fill -- position must stay open"

        # Pass 2: broker recovers. Same still-open AAPL position, same
        # breached threshold -- the exit must now actually complete, proving
        # the earlier failure didn't corrupt state or permanently drop it.
        # Broker confirms it holds the matching AAPL position now that
        # connectivity is back -- distinct from scenario 01's genuine
        # no_broker_view case, this pass is specifically about the exit
        # actually completing once the broker answers again.
        get_mock2, post_mock2 = _router(
            get_routes={
                "/candles/AAPL": _bars([100.0, 98.0, 95.0, 87.0]),
                "/broker/positions": [{"symbol": "AAPL", "qty": 10.0}],
            },
            post_routes={"/broker/order": {"status": "submitted", "order_id": "outage-recovered-1"}},
        )
        orch._http.get, orch._http.post = get_mock2, post_mock2
        position = list_open_positions(book, symbol="AAPL")[0]
        action = asyncio.run(orch._evaluate_open_position(aapl_plan, position, 87.0, 100000.0))

        assert action["action"] == "invalidation_exit"
        assert list_open_positions(book, symbol="AAPL") == []


# 40-bar deterministic price series for scenario 05 -- verified against the
# REAL dynamic_covariance/correlation_from_covariance pipeline (not guessed)
# before writing this scenario. AAA: trend + oscillation. BBB: exactly
# 0.3 * AAA at every bar -> identical log returns by construction -> real
# computed correlation ~0.99999996 (effectively 1.0). DDD: an independent,
# differently-phased oscillation with no shared trend -> real computed
# correlation ~-0.036 (genuinely uncorrelated, not just "not proven
# correlated"). Also clears dynamic_covariance's own internal min_periods
# gate (31 log-return periods, i.e. >=32 closes with the default window=63)
# -- comfortably above _compute_covariance's weaker min_len<20 check, so
# this lands nowhere near the dead zone between the two gates.
_AAA_CLOSES = [100.000000, 102.432653, 103.956349, 104.089628, 103.004964, 101.447650, 100.385273, 100.552642, 102.106200, 104.550442, 106.970960, 108.464505, 108.563797, 107.457295, 105.900563, 104.860913, 105.062467, 106.645589, 109.100869, 111.508709, 112.971822, 113.037240, 111.909355, 110.353786, 109.337299, 109.573122, 111.185502, 113.651268, 116.045891, 117.478299, 117.509967, 116.361158, 114.807333, 113.814438, 114.084605, 115.725927, 118.201624, 120.582494, 121.983934, 121.981984]
_BBB_CLOSES = [30.000000, 30.729796, 31.186905, 31.226888, 30.901489, 30.434295, 30.115582, 30.165793, 30.631860, 31.365133, 32.091288, 32.539351, 32.569139, 32.237189, 31.770169, 31.458274, 31.518740, 31.993677, 32.730261, 33.452613, 33.891547, 33.911172, 33.572807, 33.106136, 32.801190, 32.871937, 33.355650, 34.095380, 34.813767, 35.243490, 35.252990, 34.908347, 34.442200, 34.144331, 34.225381, 34.717778, 35.460487, 36.174748, 36.595180, 36.594595]
_DDD_CLOSES = [81.782415, 80.277240, 78.045095, 80.973227, 81.345938, 78.129449, 79.897356, 81.896316, 78.923895, 78.745334, 81.948249, 79.927297, 78.173197, 81.172670, 81.156551, 77.984789, 80.247949, 81.746619, 78.737764, 78.947708, 82.071201, 79.577755, 78.343924, 81.344153, 80.942618, 77.883959, 80.594748, 81.555545, 78.582181, 79.171708, 82.149621, 79.235379, 78.554547, 81.482674, 80.710101, 77.828108, 80.931047, 81.326280, 78.461790, 79.411144]


def _corr_cycle_routes(get_extra: dict, post_extra: dict):
    base_get = {
        "/broker/account": {"configured": True, "equity": 100000.0},
        "/broker/status": {"halted": False},
        "/broker/positions": [],
    }
    base_get.update(get_extra)
    base_post = {"/broker/order": {"status": "submitted", "order_id": "corr-1"}}
    base_post.update(post_extra)
    return _router(get_routes=base_get, post_routes=base_post)


class TestScenarioMultipleCorrelatedPositions:
    """the-reasoning-inefficiency/scenarios-test/05-multiple-correlated-positions/
    scenario.md -- TestRuntimeCorrelationMonitor (test_trade_plan_orchestrator.py)
    already proves the decision logic given a correlation number, by mocking
    _compute_covariance directly. This drives the REAL covariance/shrinkage
    math (vinu_tools.compute.risk.covariance) from real price history, through
    a real cycle() call -- the actual end-to-end pipeline has never been
    exercised in this suite before."""

    def test_real_correlation_math_flags_and_reduces_the_larger_side(self, book) -> None:
        # Entry price == last close for both -> zero unrealized P&L, so
        # nothing in _evaluate_open_position (invalidation/bracket-partial)
        # fires and confuses the market-value comparison this test checks.
        open_position(book, "AAA", "long", 10.0, _AAA_CLOSES[-1])
        open_position(book, "BBB", "long", 10.0, _BBB_CLOSES[-1])
        aaa_plan = _plan(symbol="AAA")
        bbb_plan = _plan(symbol="BBB")
        orch = _make_orchestrator(book)
        get_mock, post_mock = _corr_cycle_routes(
            get_extra={
                "/research/artifacts": [
                    {"artifact_id": "art_aaa", "status": "ACTIVE", "type": "trade_plan"},
                    {"artifact_id": "art_bbb", "status": "ACTIVE", "type": "trade_plan"},
                ],
                "/research/trade-plan/art_aaa": {"artifact_id": "art_aaa", "trade_plan_data": json.dumps(aaa_plan)},
                "/research/trade-plan/art_bbb": {"artifact_id": "art_bbb", "trade_plan_data": json.dumps(bbb_plan)},
                "/candles/AAA": _bars(_AAA_CLOSES),
                "/candles/BBB": _bars(_BBB_CLOSES),
                # Broker confirms it holds both matching positions --
                # reconciliation runs before the correlation check each
                # cycle, and scenario-06's fix means a confirmed-flat
                # 200-with-[] now correctly auto-closes stale positions,
                # which would wipe these out before correlation ever ran.
                "/broker/positions": [
                    {"symbol": "AAA", "qty": 10.0}, {"symbol": "BBB", "qty": 10.0},
                ],
            },
            post_extra={},
        )
        orch._http.get, orch._http.post = get_mock, post_mock

        result = asyncio.run(orch.cycle())

        assert result["status"] == "ok"
        corr_result = result["correlation_monitor"]
        assert corr_result["checked"] is True
        assert corr_result["n_flagged_pairs"] == 1
        assert corr_result["flagged"][0]["correlation"] > 0.85
        assert len(corr_result["reductions"]) == 1
        assert corr_result["reductions"][0]["symbol"] == "AAA"  # larger market value

        order_calls = [c for c in post_mock.await_args_list if "/broker/order" in c.args[0]]
        assert any(c.kwargs["json"]["symbol"] == "AAA" and c.kwargs["json"]["reduce_only"] is True for c in order_calls)
        remaining_aaa = list_open_positions(book, symbol="AAA")[0].qty
        assert remaining_aaa < 10.0  # actually reduced
        assert list_open_positions(book, symbol="BBB")[0].qty == 10.0  # untouched

    def test_real_uncorrelated_prices_do_not_trip_it(self, book) -> None:
        open_position(book, "AAA", "long", 10.0, _AAA_CLOSES[-1])
        open_position(book, "DDD", "long", 10.0, _DDD_CLOSES[-1])
        aaa_plan = _plan(symbol="AAA")
        ddd_plan = _plan(symbol="DDD")
        orch = _make_orchestrator(book)
        get_mock, post_mock = _corr_cycle_routes(
            get_extra={
                "/research/artifacts": [
                    {"artifact_id": "art_aaa", "status": "ACTIVE", "type": "trade_plan"},
                    {"artifact_id": "art_ddd", "status": "ACTIVE", "type": "trade_plan"},
                ],
                "/research/trade-plan/art_aaa": {"artifact_id": "art_aaa", "trade_plan_data": json.dumps(aaa_plan)},
                "/research/trade-plan/art_ddd": {"artifact_id": "art_ddd", "trade_plan_data": json.dumps(ddd_plan)},
                "/candles/AAA": _bars(_AAA_CLOSES),
                "/candles/DDD": _bars(_DDD_CLOSES),
                "/broker/positions": [
                    {"symbol": "AAA", "qty": 10.0}, {"symbol": "DDD", "qty": 10.0},
                ],
            },
            post_extra={},
        )
        orch._http.get, orch._http.post = get_mock, post_mock

        result = asyncio.run(orch.cycle())

        assert result["status"] == "ok"
        corr_result = result["correlation_monitor"]
        assert corr_result["checked"] is True  # covariance WAS computable -- this isn't the no-op path
        assert corr_result["n_flagged_pairs"] == 0
        assert corr_result["reductions"] == []
        assert list_open_positions(book, symbol="AAA")[0].qty == 10.0
        assert list_open_positions(book, symbol="DDD")[0].qty == 10.0


class TestScenarioBrokerStopClosedOvernight:
    """the-reasoning-inefficiency/scenarios-test/06-broker-stop-closed-overnight/
    scenario.md -- the flagged gap from scenario 01: does the system
    correctly recover when the broker-side resting stop (the catastrophic
    backstop) has already closed the account's only position before the
    next cycle even runs? Found while designing this: _fetch_broker_positions
    used to return {} for both a confirmed-flat account (a real 200 with an
    empty list) and a genuine fetch failure, making them indistinguishable
    to every caller -- so a single-position account whose only holding was
    closed overnight was never auto-corrected, and a later invalidation
    exit on that stale position would fall back to no_broker_view and send
    a real reduce_only order against nothing to reduce (the exact "opened a
    short on an already-flat account" bug _broker_close_plan's own
    docstring says it exists to prevent). Fixed in orchestrator.py:
    _fetch_broker_positions now returns None only for a genuinely unknown
    state; a confirmed 200 response (even an empty one) is a dict."""

    def test_reconciliation_auto_closes_the_stale_position_when_broker_confirms_flat(self, book) -> None:
        open_position(book, "AAPL", "long", 10.0, 100.0)
        orch = _make_orchestrator(book)
        # A mild move that does NOT trip invalidation this cycle -- the
        # realistic case where nothing but end-of-cycle reconciliation
        # would ever notice the broker-side stop already fired overnight.
        get_mock, post_mock = _router(
            get_routes={"/candles/AAPL": _bars([100.0, 101.0]), "/broker/positions": []},
            post_routes={},
        )
        orch._http.get, orch._http.post = get_mock, post_mock

        recon = asyncio.run(orch._reconcile_book_with_broker({"AAPL": 101.0}))

        assert recon["drift_detected"] is True
        assert recon["corrections"][0]["action"] == "closed_to_match_broker"
        assert list_open_positions(book, symbol="AAPL") == []

    def test_invalidation_exit_on_the_same_stale_position_never_sends_a_phantom_order(self, book) -> None:
        """If invalidation ALSO happens to fire the same cycle reconciliation
        would have caught this on (before reconciliation runs -- it's later
        in cycle()), _broker_close_plan must independently reach the same
        safe conclusion: broker_flat, book-only close, no order sent --
        not no_broker_view, which used to send a real sell into nothing."""
        open_position(book, "AAPL", "long", 10.0, 100.0)
        plan = _plan(invalidation_conditions=[
            {"metric": "unrealized_pnl_pct", "operator": "<=", "threshold": -0.08, "action": "exit", "action_params": {}},
        ])
        orch = _make_orchestrator(book)
        get_mock, post_mock = _router(
            get_routes={"/candles/AAPL": _bars([100.0, 90.0]), "/broker/positions": []},
            post_routes={"/broker/order": {"status": "submitted", "order_id": "should-never-be-called"}},
        )
        orch._http.get, orch._http.post = get_mock, post_mock
        position = list_open_positions(book, symbol="AAPL")[0]

        action = asyncio.run(orch._evaluate_open_position(plan, position, 90.0, 100000.0))

        assert action["action"] == "invalidation_exit_book_only"
        post_mock.assert_not_awaited()  # no phantom order against a flat account
        assert list_open_positions(book, symbol="AAPL") == []

    def test_genuine_broker_failure_still_falls_back_to_no_broker_view(self, book) -> None:
        """The still-correct half: a real transport error is genuinely
        unknown (not a confirmed flat), and must still fall back to
        closing the full book qty via a real order -- scenario 01's
        already-proven behavior, now reached only by an actual failure
        instead of being conflated with the confirmed-flat case above."""
        open_position(book, "AAPL", "long", 10.0, 100.0)
        plan = _plan(invalidation_conditions=[
            {"metric": "unrealized_pnl_pct", "operator": "<=", "threshold": -0.08, "action": "exit", "action_params": {}},
        ])
        orch = _make_orchestrator(book)
        get_mock, post_mock = _router_with_errors(
            get_routes={"/candles/AAPL": _bars([100.0, 90.0])},
            get_errors={"/broker/positions"},
            post_routes={"/broker/order": {"status": "submitted", "order_id": "no-view-exit"}},
            post_errors=set(),
        )
        orch._http.get, orch._http.post = get_mock, post_mock
        position = list_open_positions(book, symbol="AAPL")[0]

        action = asyncio.run(orch._evaluate_open_position(plan, position, 90.0, 100000.0))

        assert action["action"] == "invalidation_exit"
        order_call = post_mock.await_args_list[0]
        assert order_call.kwargs["json"]["reduce_only"] is True
        assert list_open_positions(book, symbol="AAPL") == []
