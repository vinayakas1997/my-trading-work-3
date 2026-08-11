"""Tests for SubmitThesisTool -- Phase 6 (New-talk-agents/new-thinking/
new-restructure/phases/phase-6-thesis-intake/). Mocks TeamManager (tested
in isolation elsewhere, e.g. test_team.py); the vinu-research hypothesis
reads/writes go through the real in-process HypothesisRegistry first (see
broker/research_link.py), with an HTTP-mocked fallback path exercised
separately, so this file focuses on the orchestration this tool itself
adds: THGATE-before-any-LLM-call, the human-hypothesis write, the
shared-counter write, and the hand-off to research.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vinu_agent.storage.ticker_ledger import TickerLedgerStore
from vinu_agent.tools.submit_thesis_tool import SubmitThesisTool
from vinu_research.hypothesis_registry import HypothesisRegistry
from vinu_research.models import Hypothesis


@pytest.fixture
def ticker_ledger_store():
    path = Path(tempfile.mktemp(suffix=".db"))
    store = TickerLedgerStore(path)
    yield store
    store.close()
    try:
        path.unlink(missing_ok=True)
    except PermissionError:
        pass


@pytest.fixture
def hypothesis_registry() -> HypothesisRegistry:
    return HypothesisRegistry(path=Path(tempfile.mktemp(suffix=".json")))


def _tool(ticker_ledger_store) -> SubmitThesisTool:
    tool = SubmitThesisTool()
    tool._teams_dir = "/fake/teams"
    tool._full_registry = MagicMock()
    tool._llm = MagicMock()
    tool._ticker_ledger_store = ticker_ledger_store
    tool._services_config = {"vinu_research": "http://research-api:8087"}
    return tool


def _http_get_empty_hypotheses(*a, **kw):
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = {"hypotheses": []}
    return resp


def _force_in_process_unavailable():
    return patch(
        "vinu_agent.broker.research_link.get_hypothesis_registry",
        side_effect=RuntimeError("not available"),
    )


class TestSubmitThesisToolWiring:
    def test_not_wired_errors(self) -> None:
        tool = SubmitThesisTool()
        result = json.loads(tool.execute(ticker="AAPL", title="t", thesis="th"))
        assert result["status"] == "error"


class TestThgateBlocksBeforeAnyTeamRun:
    def test_near_duplicate_blocks_before_team_manager_constructed(self, ticker_ledger_store, hypothesis_registry) -> None:
        tool = _tool(ticker_ledger_store)
        existing = Hypothesis.create(
            title="t", thesis="AAPL drifts after earnings surprises for about a week", universe=["AAPL"],
        )
        hypothesis_registry.create(existing)

        with patch(
            "vinu_agent.broker.research_link.get_hypothesis_registry", return_value=hypothesis_registry,
        ), patch("vinu_agent.agent.team.TeamManager") as mock_manager_cls:
            result = json.loads(tool.execute(
                ticker="AAPL", title="t",
                thesis="AAPL drifts after earnings surprises for about a week or so",
            ))

        assert result["status"] == "blocked_by_thgate"
        assert result["matched_hypothesis_id"] == existing.hypothesis_id
        mock_manager_cls.assert_not_called()  # no LLM call at all -- THGATE ran first

    def test_kcap_blocks_before_team_manager_constructed(self, ticker_ledger_store, hypothesis_registry) -> None:
        tool = _tool(ticker_ledger_store)
        for i in range(3):
            ticker_ledger_store.add_event(
                ticker="AAPL", stage="research", event_type="candidate_proposed",
                text=f"idea {i}", source="watchlist",
            )

        with patch(
            "vinu_agent.broker.research_link.get_hypothesis_registry", return_value=hypothesis_registry,
        ), patch("vinu_agent.agent.team.TeamManager") as mock_manager_cls:
            result = json.loads(tool.execute(ticker="AAPL", title="t", thesis="a fresh theory"))

        assert result["status"] == "blocked_by_thgate"
        assert "cap" in result["reason"]
        mock_manager_cls.assert_not_called()

    def test_near_duplicate_check_falls_back_to_http_when_in_process_raises(self, ticker_ledger_store) -> None:
        tool = _tool(ticker_ledger_store)

        def fake_get(*a, **kw):
            resp = MagicMock()
            resp.raise_for_status.return_value = None
            resp.json.return_value = {"hypotheses": [
                {"hypothesis_id": "hyp_1", "thesis": "AAPL drifts after earnings surprises for about a week"},
            ]}
            return resp

        with _force_in_process_unavailable(), patch("httpx.get", side_effect=fake_get):
            with patch("vinu_agent.agent.team.TeamManager") as mock_manager_cls:
                result = json.loads(tool.execute(
                    ticker="AAPL", title="t",
                    thesis="AAPL drifts after earnings surprises for about a week or so",
                ))

        assert result["status"] == "blocked_by_thgate"
        assert result["matched_hypothesis_id"] == "hyp_1"
        mock_manager_cls.assert_not_called()


class TestWorthCheckingFlow:
    def _mock_team_manager(self, review_content: str, handoff_status: str = "completed"):
        instances = []

        def factory(*args, **kwargs):
            m = MagicMock()
            if not instances:
                m.run.return_value = {"status": "completed", "content": review_content}
            else:
                m.run.return_value = {"status": handoff_status, "content": "research team is on it"}
            instances.append(m)
            return m
        return factory

    def test_worth_checking_writes_real_human_hypothesis_and_candidate_event(self, ticker_ledger_store, hypothesis_registry) -> None:
        tool = _tool(ticker_ledger_store)
        review_content = """Looks solid.

```json
{"verdict": "WORTH_CHECKING", "ticker": "AAPL", "title": "Earnings drift", "thesis": "text", "reasoning": "real evidence cited here"}
```
"""
        with patch("vinu_agent.broker.research_link.get_hypothesis_registry", return_value=hypothesis_registry):
            with patch("vinu_agent.agent.team.TeamManager", side_effect=self._mock_team_manager(review_content)):
                result = json.loads(tool.execute(ticker="AAPL", title="Earnings drift", thesis="text"))

        assert result["status"] == "worth_checking"
        hypothesis_id = result["hypothesis_id"]
        assert hypothesis_id

        stored = hypothesis_registry.get(hypothesis_id)
        assert stored is not None
        assert stored.source == "human"

        events = ticker_ledger_store.get_events("AAPL")
        assert len(events) == 1
        assert events[0].event_type == "candidate_proposed"
        assert events[0].source == "human"
        assert events[0].ref_id == hypothesis_id

    def test_does_not_hold_up_never_writes_hypothesis_or_event(self, ticker_ledger_store, hypothesis_registry) -> None:
        tool = _tool(ticker_ledger_store)
        review_content = """Doesn't hold up.

```json
{"verdict": "DOES_NOT_HOLD_UP", "ticker": "AAPL", "title": "t", "thesis": "text", "reasoning": "contradicted by real evidence"}
```
"""
        with patch("vinu_agent.broker.research_link.get_hypothesis_registry", return_value=hypothesis_registry):
            with patch("vinu_agent.agent.team.TeamManager", side_effect=self._mock_team_manager(review_content)):
                result = json.loads(tool.execute(ticker="AAPL", title="t", thesis="text"))

        assert result["status"] == "does_not_hold_up"
        assert hypothesis_registry.count() == 0  # no human-hypothesis write attempted
        assert ticker_ledger_store.get_events("AAPL") == []

    def test_worth_checking_hands_off_to_research_team(self, ticker_ledger_store, hypothesis_registry) -> None:
        """Confirmed by call target -- the same 'research' team name Phase
        1's sweep-engine upgrade targets, not a separate/new loop."""
        tool = _tool(ticker_ledger_store)
        review_content = """OK.

```json
{"verdict": "WORTH_CHECKING", "ticker": "AAPL", "title": "t", "thesis": "text", "reasoning": "evidence"}
```
"""
        with patch("vinu_agent.broker.research_link.get_hypothesis_registry", return_value=hypothesis_registry):
            with patch("vinu_agent.agent.team.TeamManager") as mock_manager_cls:
                mock_manager_cls.side_effect = self._mock_team_manager(review_content)
                tool.execute(ticker="AAPL", title="t", thesis="text")

        team_dirs = [str(call.args[0]) for call in mock_manager_cls.call_args_list]
        assert any("thesis_intake" in d for d in team_dirs)
        assert any(d.endswith("research") or "research" in d for d in team_dirs)
        assert mock_manager_cls.call_count == 2

    def test_human_hypothesis_write_failure_does_not_lose_the_review(self, ticker_ledger_store) -> None:
        """Best-effort: the review already completed successfully -- a
        failure recording the hypothesis (both in-process AND HTTP down)
        must not turn a real WORTH_CHECKING verdict into an error."""
        tool = _tool(ticker_ledger_store)
        review_content = """OK.

```json
{"verdict": "WORTH_CHECKING", "ticker": "AAPL", "title": "t", "thesis": "text", "reasoning": "evidence"}
```
"""
        with _force_in_process_unavailable():
            with patch("httpx.get", side_effect=_http_get_empty_hypotheses):
                with patch("httpx.post", side_effect=ConnectionError("vinu-research down")):
                    with patch("vinu_agent.agent.team.TeamManager", side_effect=self._mock_team_manager(review_content)):
                        result = json.loads(tool.execute(ticker="AAPL", title="t", thesis="text"))

        assert result["status"] == "worth_checking"
        assert result["hypothesis_id"] == ""

    def test_worth_checking_falls_back_to_http_when_in_process_raises(self, ticker_ledger_store) -> None:
        tool = _tool(ticker_ledger_store)
        review_content = """Looks solid.

```json
{"verdict": "WORTH_CHECKING", "ticker": "AAPL", "title": "Earnings drift", "thesis": "text", "reasoning": "real evidence cited here"}
```
"""
        with _force_in_process_unavailable():
            with patch("httpx.get", side_effect=_http_get_empty_hypotheses):
                with patch("httpx.post") as mock_post:
                    mock_post.return_value.raise_for_status.return_value = None
                    mock_post.return_value.json.return_value = {"hypothesis_id": "hyp_new1", "source": "human"}
                    with patch("vinu_agent.agent.team.TeamManager", side_effect=self._mock_team_manager(review_content)):
                        result = json.loads(tool.execute(ticker="AAPL", title="Earnings drift", thesis="text"))

        assert result["status"] == "worth_checking"
        assert result["hypothesis_id"] == "hyp_new1"
        human_calls = [c for c in mock_post.call_args_list if "/hypotheses/human" in c.args[0]]
        assert len(human_calls) == 1
