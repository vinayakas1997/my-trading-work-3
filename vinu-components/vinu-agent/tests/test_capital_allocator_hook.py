"""Direct tests for apply_capital_allocator_decision -- Phase 2's PEND->
ACTIVE funding application plus Phase 3's Kill-Switch gate immediately
before it (New-talk-agents/new-thinking/new-restructure/phases/
phase-3-kill-switch/). See agent/capital_allocator_hook.py.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vinu_agent.agent.capital_allocator_hook import apply_capital_allocator_decision
from vinu_agent.storage.ticker_ledger import TickerLedgerStore
from vinu_research.models import Artifact, ArtifactStatus
from vinu_research.storage.strategy_store import SqliteStrategyStore


@pytest.fixture
def strategy_store():
    store_path = Path(tempfile.mktemp(suffix=".db"))
    store = SqliteStrategyStore(store_path)
    yield store
    store.close()
    store_path.unlink(missing_ok=True)


@pytest.fixture
def ticker_ledger_store():
    ledger_path = Path(tempfile.mktemp(suffix=".db"))
    store = TickerLedgerStore(ledger_path)
    yield store
    store.close()
    ledger_path.unlink(missing_ok=True)


def _pend_artifact(strategy_store: SqliteStrategyStore, symbol: str, approved_size: float = 20000.0) -> str:
    artifact = Artifact.create("strategy", f"{symbol}-test", universe=[symbol])
    strategy_store.upsert_artifact(artifact)
    strategy_store.mark_benching(artifact.artifact_id)
    strategy_store.mark_pend(artifact.artifact_id, approved_size=approved_size)
    return artifact.artifact_id


def _active_artifact(strategy_store: SqliteStrategyStore, symbol: str, approved_size: float = 20000.0) -> str:
    artifact_id = _pend_artifact(strategy_store, symbol, approved_size=approved_size)
    with patch("vinu_agent.broker.kill_switch.is_trading_halted", return_value=False):
        strategy_store.mark_active(artifact_id)
    return artifact_id


def _content(candidates: list[dict] | None = None, unwind: list[dict] | None = None) -> str:
    body: dict = {"budget": 100000, "candidates": candidates or []}
    if unwind is not None:
        body["unwind"] = unwind
    return f"""Funding decision.

```json
{json.dumps(body)}
```
"""


class TestKillSwitchGate:
    def test_mark_active_blocked_when_globally_halted(self, strategy_store) -> None:
        artifact_id = _pend_artifact(strategy_store, "AAPL")
        content = _content([{"artifact_id": artifact_id, "funded": True, "amount": 15000.0}])

        with patch("vinu_agent.broker.kill_switch.is_trading_halted", return_value=True):
            apply_capital_allocator_decision(content, strategy_store=strategy_store)

        assert strategy_store.get_artifact(artifact_id).status == ArtifactStatus.PENDBLOCK

    def test_mark_active_proceeds_when_not_halted(self, strategy_store) -> None:
        artifact_id = _pend_artifact(strategy_store, "AAPL")
        content = _content([{"artifact_id": artifact_id, "funded": True, "amount": 15000.0}])

        with patch("vinu_agent.broker.kill_switch.is_trading_halted", return_value=False):
            apply_capital_allocator_decision(content, strategy_store=strategy_store)

        assert strategy_store.get_artifact(artifact_id).status == ArtifactStatus.ACTIVE

    def test_scoped_halt_blocks_only_matching_scope(self, strategy_store) -> None:
        aapl_id = _pend_artifact(strategy_store, "AAPL")
        msft_id = _pend_artifact(strategy_store, "MSFT")
        content = _content([
            {"artifact_id": aapl_id, "funded": True, "amount": 10000.0},
            {"artifact_id": msft_id, "funded": True, "amount": 10000.0},
        ])

        def fake_halted(scope=None):
            return scope == "AAPL"

        with patch("vinu_agent.broker.kill_switch.is_trading_halted", side_effect=fake_halted):
            apply_capital_allocator_decision(content, strategy_store=strategy_store)

        assert strategy_store.get_artifact(aapl_id).status == ArtifactStatus.PENDBLOCK
        assert strategy_store.get_artifact(msft_id).status == ArtifactStatus.ACTIVE

    def test_broker_status_unreachable_defaults_to_halted(self, strategy_store) -> None:
        artifact_id = _pend_artifact(strategy_store, "AAPL")
        content = _content([{"artifact_id": artifact_id, "funded": True, "amount": 15000.0}])

        with patch("vinu_agent.broker.kill_switch.is_trading_halted", side_effect=ConnectionError("down")):
            apply_capital_allocator_decision(content, strategy_store=strategy_store)

        assert strategy_store.get_artifact(artifact_id).status == ArtifactStatus.PENDBLOCK

    def test_pendblock_transition_writes_distinct_ticker_ledger_event(
        self, strategy_store, ticker_ledger_store
    ) -> None:
        artifact_id = _pend_artifact(strategy_store, "AAPL")
        content = _content([{"artifact_id": artifact_id, "funded": True, "amount": 15000.0}])

        with patch("vinu_agent.broker.kill_switch.is_trading_halted", return_value=True):
            apply_capital_allocator_decision(
                content, strategy_store=strategy_store, ticker_ledger_store=ticker_ledger_store,
            )

        events = ticker_ledger_store.get_events("AAPL")
        assert len(events) == 1
        assert events[0].event_type == "PENDBLOCK"
        assert events[0].event_type != "funded"  # distinct from an ordinary funded transition

    def test_pendblock_auto_retries_after_resume_no_manual_action(self, strategy_store) -> None:
        artifact_id = _pend_artifact(strategy_store, "AAPL")
        content = _content([{"artifact_id": artifact_id, "funded": True, "amount": 15000.0}])

        with patch("vinu_agent.broker.kill_switch.is_trading_halted", return_value=True):
            apply_capital_allocator_decision(content, strategy_store=strategy_store)
        assert strategy_store.get_artifact(artifact_id).status == ArtifactStatus.PENDBLOCK

        # Resume, then the SAME decision content is naturally re-produced
        # by the next cadence run (the manager includes PENDBLOCK
        # candidates in its next batch alongside PEND ones) -- no separate
        # "unstick" call, just the ordinary funding path re-running.
        with patch("vinu_agent.broker.kill_switch.is_trading_halted", return_value=False):
            apply_capital_allocator_decision(content, strategy_store=strategy_store)
        assert strategy_store.get_artifact(artifact_id).status == ArtifactStatus.ACTIVE

    def test_not_funded_candidates_never_reach_the_kill_switch_check(self, strategy_store) -> None:
        """A candidate the manager reported as not-funded should never
        transition at all -- the kill-switch gate only applies to the
        real mark_active path."""
        artifact_id = _pend_artifact(strategy_store, "AAPL")
        content = _content([{"artifact_id": artifact_id, "funded": False, "amount": 0.0, "reason": "budget exhausted"}])

        with patch("vinu_agent.broker.kill_switch.is_trading_halted") as mock_halted:
            apply_capital_allocator_decision(content, strategy_store=strategy_store)

        mock_halted.assert_not_called()
        assert strategy_store.get_artifact(artifact_id).status == ArtifactStatus.PEND


class TestUnwindRequests:
    """The rebalancer role (mermaid-explanation.md section 5): the
    manager's optional "unwind" list -> a REQUEST to vinu-live, gated by
    rebalance_guard.check_rebalance_allowed, never a direct action."""

    def test_active_artifact_allowed_posts_to_vinu_live(self, strategy_store, ticker_ledger_store) -> None:
        artifact_id = _active_artifact(strategy_store, "AAPL")
        content = _content(unwind=[{"artifact_id": artifact_id, "reason": "weaker calibration"}])

        mock_resp = MagicMock(status_code=200)
        mock_resp.raise_for_status = MagicMock()
        with patch("vinu_agent.agent.rebalance_guard.check_rebalance_allowed", return_value=True), \
             patch("httpx.post", return_value=mock_resp) as mock_post:
            apply_capital_allocator_decision(
                content, strategy_store=strategy_store, ticker_ledger_store=ticker_ledger_store,
                services_config={"vinu_live": "http://vinu-live:8091"},
            )

        mock_post.assert_called_once()
        url, kwargs = mock_post.call_args[0][0], mock_post.call_args[1]
        assert url == "http://vinu-live:8091/live/trade-plan/rebalance-request"
        assert kwargs["json"] == {"symbol": "AAPL", "reason": "weaker calibration"}

        events = ticker_ledger_store.get_events("AAPL")
        assert len(events) == 1
        assert events[0].event_type == "rebalance_requested"
        assert events[0].ref_id == artifact_id

    def test_blocked_by_kill_switch_does_not_post(self, strategy_store, ticker_ledger_store) -> None:
        artifact_id = _active_artifact(strategy_store, "AAPL")
        content = _content(unwind=[{"artifact_id": artifact_id, "reason": "weaker calibration"}])

        with patch("vinu_agent.agent.rebalance_guard.check_rebalance_allowed", return_value=False), \
             patch("httpx.post") as mock_post:
            apply_capital_allocator_decision(
                content, strategy_store=strategy_store, ticker_ledger_store=ticker_ledger_store,
            )

        mock_post.assert_not_called()
        events = ticker_ledger_store.get_events("AAPL")
        assert len(events) == 1
        assert events[0].event_type == "rebalance_blocked"

    def test_non_active_artifact_is_skipped(self, strategy_store, ticker_ledger_store) -> None:
        """A PEND (or any non-ACTIVE) artifact isn't a real position --
        nothing real to unwind, so no request should ever be sent."""
        artifact_id = _pend_artifact(strategy_store, "AAPL")
        content = _content(unwind=[{"artifact_id": artifact_id, "reason": "weaker calibration"}])

        with patch("vinu_agent.agent.rebalance_guard.check_rebalance_allowed") as mock_allowed, \
             patch("httpx.post") as mock_post:
            apply_capital_allocator_decision(
                content, strategy_store=strategy_store, ticker_ledger_store=ticker_ledger_store,
            )

        mock_allowed.assert_not_called()
        mock_post.assert_not_called()
        assert ticker_ledger_store.get_events("AAPL") == []

    def test_vinu_live_unreachable_logs_failure_but_does_not_raise(self, strategy_store, ticker_ledger_store) -> None:
        artifact_id = _active_artifact(strategy_store, "AAPL")
        content = _content(unwind=[{"artifact_id": artifact_id, "reason": "weaker calibration"}])

        with patch("vinu_agent.agent.rebalance_guard.check_rebalance_allowed", return_value=True), \
             patch("httpx.post", side_effect=ConnectionError("vinu-live down")):
            apply_capital_allocator_decision(  # must not raise
                content, strategy_store=strategy_store, ticker_ledger_store=ticker_ledger_store,
            )

        events = ticker_ledger_store.get_events("AAPL")
        assert len(events) == 1
        assert events[0].event_type == "rebalance_request_failed"

    def test_funding_and_unwind_both_processed_in_one_decision(self, strategy_store, ticker_ledger_store) -> None:
        funded_id = _pend_artifact(strategy_store, "MSFT")
        unwind_id = _active_artifact(strategy_store, "AAPL")
        content = _content(
            candidates=[{"artifact_id": funded_id, "funded": True, "amount": 10000.0}],
            unwind=[{"artifact_id": unwind_id, "reason": "weaker calibration"}],
        )

        mock_resp = MagicMock(status_code=200)
        mock_resp.raise_for_status = MagicMock()
        with patch("vinu_agent.broker.kill_switch.is_trading_halted", return_value=False), \
             patch("vinu_agent.agent.rebalance_guard.check_rebalance_allowed", return_value=True), \
             patch("httpx.post", return_value=mock_resp):
            apply_capital_allocator_decision(
                content, strategy_store=strategy_store, ticker_ledger_store=ticker_ledger_store,
            )

        assert strategy_store.get_artifact(funded_id).status == ArtifactStatus.ACTIVE
        assert any(e.event_type == "rebalance_requested" for e in ticker_ledger_store.get_events("AAPL"))

    def test_no_unwind_key_makes_no_rebalance_calls(self, strategy_store) -> None:
        artifact_id = _pend_artifact(strategy_store, "AAPL")
        content = _content(candidates=[{"artifact_id": artifact_id, "funded": False, "amount": 0.0}])

        with patch("vinu_agent.agent.rebalance_guard.check_rebalance_allowed") as mock_allowed, \
             patch("httpx.post") as mock_post:
            apply_capital_allocator_decision(content, strategy_store=strategy_store)

        mock_allowed.assert_not_called()
        mock_post.assert_not_called()

    def test_missing_artifact_id_in_unwind_entry_is_skipped_not_raised(self, strategy_store) -> None:
        content = _content(unwind=[{"reason": "no artifact_id here"}])
        apply_capital_allocator_decision(content, strategy_store=strategy_store)  # must not raise
