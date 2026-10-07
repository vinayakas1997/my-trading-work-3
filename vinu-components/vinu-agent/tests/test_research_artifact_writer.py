"""Tests for turning a research team's PASS verdict into a real
vinu-research Artifact (closing the gap: a PASS previously had no effect
on OrderGuard's active-artifact check, since nothing wrote to
strategy_store.db from vinu-agent's side)."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from vinu_agent.agent.research_artifact_writer import write_artifact_from_research_pass
from vinu_research.models import ArtifactStatus
from vinu_research.storage.strategy_store import SqliteStrategyStore


@pytest.fixture(autouse=True)
def _no_real_bar_validation(monkeypatch):
    """The writer asks vinu-research to re-test the strategy on every bar size; these tests do not run that service."""
    monkeypatch.setattr("vinu_agent.agent.research_artifact_writer.validate_on_all_bars", lambda *a, **k: None)


@pytest.fixture
def store() -> SqliteStrategyStore:
    tmp = tempfile.mktemp(suffix=".db")
    s = SqliteStrategyStore(Path(tmp))
    yield s
    s.close()
    Path(tmp).unlink(missing_ok=True)


_PASS_CONTENT = """
Verdict: PASS. This strategy trades AAPL on a mean-reversion signal.

```json
{
  "verdict": "PASS",
  "symbol": "AAPL",
  "sharpe": 0.85,
  "max_drawdown": -0.12,
  "strategy_code": "class Strategy:\\n    def generate_weights(self, data):\\n        pass"
}
```
"""

_STOP_CONTENT = """
Verdict: STOP, the backtest wasn't statistically significant.

```json
{"verdict": "STOP", "symbol": "AAPL", "sharpe": 0.1, "max_drawdown": -0.4, "strategy_code": "class Strategy:\\n    pass"}
```
"""

_PASS_WITH_ANGLES_CONTENT = """
Verdict: PASS. Informed by patchtst and shock_personality angle data.

```json
{
  "verdict": "PASS",
  "symbol": "AAPL",
  "sharpe": 0.85,
  "max_drawdown": -0.12,
  "strategy_code": "class Strategy:\\n    pass",
  "angles_used": ["patchtst", "shock_personality"]
}
```
"""


class TestWriteArtifactFromResearchPass:
    def test_pass_writes_a_real_artifact(self, store: SqliteStrategyStore) -> None:
        artifact_id = write_artifact_from_research_pass(
            _PASS_CONTENT, strategy_store=store, source_run_id="run123",
        )
        assert artifact_id is not None

        fetched = store.get_artifact(artifact_id)
        assert fetched is not None
        assert fetched.status == ArtifactStatus.BENCHING
        assert fetched.universe == ["AAPL"]
        assert fetched.initial_sharpe == pytest.approx(0.85)
        assert fetched.initial_max_dd == pytest.approx(-0.12)
        assert "generate_weights" in fetched.strategy_code

    def test_stop_writes_nothing(self, store: SqliteStrategyStore) -> None:
        artifact_id = write_artifact_from_research_pass(
            _STOP_CONTENT, strategy_store=store, source_run_id="run123",
        )
        assert artifact_id is None
        assert store.list_artifacts() == []

    def test_missing_json_block_writes_nothing_and_does_not_raise(
        self, store: SqliteStrategyStore,
    ) -> None:
        artifact_id = write_artifact_from_research_pass(
            "PASS but no json block here.", strategy_store=store,
        )
        assert artifact_id is None

    def test_malformed_json_does_not_raise(self, store: SqliteStrategyStore) -> None:
        content = "PASS\n```json\n{not valid json\n```"
        artifact_id = write_artifact_from_research_pass(content, strategy_store=store)
        assert artifact_id is None

    def test_store_failure_is_swallowed_not_raised(self) -> None:
        class _BrokenStore:
            def upsert_artifact(self, artifact):
                raise OSError("disk full")

        artifact_id = write_artifact_from_research_pass(
            _PASS_CONTENT, strategy_store=_BrokenStore(),
        )
        assert artifact_id is None

    def test_missing_symbol_or_code_skips_write(self, store: SqliteStrategyStore) -> None:
        content = '```json\n{"verdict": "PASS", "symbol": "", "sharpe": 0.5, "strategy_code": ""}\n```'
        artifact_id = write_artifact_from_research_pass(content, strategy_store=store)
        assert artifact_id is None

    def test_angles_used_populates_origin_angles(self, store: SqliteStrategyStore) -> None:
        artifact_id = write_artifact_from_research_pass(
            _PASS_WITH_ANGLES_CONTENT, strategy_store=store, source_run_id="run123",
        )
        fetched = store.get_artifact(artifact_id)
        assert fetched.origin_angles == ["patchtst", "shock_personality"]

    def test_no_angles_used_key_defaults_to_empty_list(self, store: SqliteStrategyStore) -> None:
        artifact_id = write_artifact_from_research_pass(
            _PASS_CONTENT, strategy_store=store, source_run_id="run123",
        )
        fetched = store.get_artifact(artifact_id)
        assert fetched.origin_angles == []

    def test_malformed_angles_used_is_ignored_not_raised(self, store: SqliteStrategyStore) -> None:
        content = """```json
{"verdict": "PASS", "symbol": "AAPL", "sharpe": 0.5, "strategy_code": "x", "angles_used": "not-a-list"}
```"""
        artifact_id = write_artifact_from_research_pass(content, strategy_store=store)
        fetched = store.get_artifact(artifact_id)
        assert fetched.origin_angles == []


def _row(interval, *, eligible, sharpe=0.9, deflated=1.2, trades=60):
    return {"interval": interval, "tested": True, "eligible": eligible, "reasons": [] if eligible else ["too few trades"],
            "sharpe": sharpe, "max_drawdown": -0.08, "deflated_sharpe": deflated, "holdout_passed": True,
            "stress_test_passed": True, "pbo": None, "trade_count": trades}


class TestBarEvidenceDecidesTheArtifact:
    def test_numbers_and_bar_size_come_from_the_measurement_not_the_models_text(self, store) -> None:
        rows = [_row("1d", eligible=False), _row("4h", eligible=True, sharpe=1.4, deflated=1.7), _row("15m", eligible=True)]
        evidence = {"bars": rows, "passing_bars": ["4h", "15m"], "chosen": rows[1], "chosen_bar": "4h"}
        artifact_id = write_artifact_from_research_pass(
            _PASS_CONTENT, strategy_store=store, source_run_id="r1", bar_validator=lambda *a: evidence,
        )
        a = store.get_artifact(artifact_id)
        assert a.status == ArtifactStatus.BENCHING
        assert a.bar_interval == "4h"
        assert a.initial_sharpe == pytest.approx(1.4)          # the model typed 0.85
        assert a.deflated_sharpe == pytest.approx(1.7)
        assert (a.holdout_passed, a.stress_test_passed) == (True, True)
        import json
        assert json.loads(a.bar_evidence)["passing_bars"] == ["4h", "15m"]

    def test_no_bar_size_clears_the_bar_so_the_artifact_is_disabled_with_the_table(self, store) -> None:
        rows = [_row("1d", eligible=False, sharpe=0.2), _row("1h", eligible=False, sharpe=0.5)]
        evidence = {"bars": rows, "passing_bars": [], "chosen": None, "chosen_bar": None}
        artifact_id = write_artifact_from_research_pass(
            _PASS_CONTENT, strategy_store=store, source_run_id="r2", bar_validator=lambda *a: evidence,
        )
        a = store.get_artifact(artifact_id)
        assert a.status == ArtifactStatus.DISABLED and a.bar_interval == ""
        assert "too few trades" in a.bar_evidence

    def test_unreachable_validation_leaves_it_unverified_and_the_models_numbers_unusable(self, store) -> None:
        from vinu_research.config import ResearchConfig
        from vinu_research.promotion import meets_promotion_bar

        artifact_id = write_artifact_from_research_pass(
            _PASS_CONTENT, strategy_store=store, source_run_id="r3", bar_validator=lambda *a: None,
        )
        a = store.get_artifact(artifact_id)
        assert a.status == ArtifactStatus.BENCHING and a.bar_interval == ""
        assert not meets_promotion_bar(a, ResearchConfig()).eligible      # fails closed

    def test_a_validation_error_answer_is_unverified_too(self, store) -> None:
        artifact_id = write_artifact_from_research_pass(
            _PASS_CONTENT, strategy_store=store, source_run_id="r4",
            bar_validator=lambda *a: {"error": "HTTP 422: strategy_code must define a class named UserStrategy"},
        )
        a = store.get_artifact(artifact_id)
        assert "UserStrategy" in a.bar_evidence and a.status == ArtifactStatus.BENCHING


class TestCriticIsAdviceCodeDecides:
    def test_a_stop_whose_strategy_clears_the_bar_on_some_bar_size_still_becomes_an_artifact(self, store) -> None:
        row = _row("1h", eligible=True, sharpe=1.1, deflated=1.3)
        evidence = {"bars": [row], "passing_bars": ["1h"], "chosen": row, "chosen_bar": "1h"}
        artifact_id = write_artifact_from_research_pass(
            _STOP_CONTENT, strategy_store=store, source_run_id="s1", bar_validator=lambda *a: evidence,
        )
        a = store.get_artifact(artifact_id)
        assert a.status == ArtifactStatus.BENCHING and a.bar_interval == "1h"

    def test_a_stop_that_no_bar_size_clears_writes_nothing(self, store) -> None:
        evidence = {"bars": [_row("1d", eligible=False)], "passing_bars": [], "chosen": None, "chosen_bar": None}
        assert write_artifact_from_research_pass(
            _STOP_CONTENT, strategy_store=store, source_run_id="s2", bar_validator=lambda *a: evidence,
        ) is None
        assert store.list_artifacts() == []

    def test_a_stop_is_not_tested_when_the_validation_cannot_run(self, store) -> None:
        assert write_artifact_from_research_pass(
            _STOP_CONTENT, strategy_store=store, source_run_id="s3", bar_validator=lambda *a: None,
        ) is None


def test_a_null_strategy_code_is_no_strategy_not_the_text_none(store) -> None:
    content = '```json\n{"verdict": "STOP", "symbol": "AMD", "sharpe": null, "max_drawdown": null, "strategy_code": null}\n```'
    called = []
    assert write_artifact_from_research_pass(
        content, strategy_store=store, bar_validator=lambda *a: called.append(a),
    ) is None
    assert called == [] and store.list_artifacts() == []


def _all_session_row(hints, *, interval="1h"):
    return {"interval": interval, "session": "all", "tested": True, "eligible": True, "reasons": [], "sharpe": 1.3,
            "max_drawdown": -0.1, "deflated_sharpe": 1.4, "holdout_passed": True, "stress_test_passed": True, "pbo": None,
            "pbo_waived": True, "trade_count": 90, "session_hints": hints}


class TestTradingSessionsFromTheMeasurement:
    def test_a_regular_hours_pass_approves_the_regular_session_only(self, store) -> None:
        row = _row("1d", eligible=True)
        evidence = {"bars": [row], "passing_bars": ["1d"], "chosen": row, "chosen_bar": "1d"}
        a = store.get_artifact(write_artifact_from_research_pass(_PASS_CONTENT, strategy_store=store, source_run_id="t1",
                                                                  bar_validator=lambda *x: evidence))
        assert a.trading_sessions == "regular"

    def test_an_all_session_pass_approves_the_sessions_whose_verdict_is_trade_or_reduce(self, store) -> None:
        hints = {"premarket": {"verdict": "avoid", "size_multiplier": 0.0}, "regular": {"verdict": "trade", "size_multiplier": 1.0},
                 "afterhours": {"verdict": "insufficient_data", "size_multiplier": 0.0},
                 "overnight": {"verdict": "reduce", "size_multiplier": 0.5}}
        row = _all_session_row(hints)
        evidence = {"bars": [row], "passing_bars": ["1h"], "chosen": row, "chosen_bar": "1h", "chosen_session": "all"}
        a = store.get_artifact(write_artifact_from_research_pass(_PASS_CONTENT, strategy_store=store, source_run_id="t2",
                                                                  bar_validator=lambda *x: evidence))
        assert a.trading_sessions == "regular,overnight" and a.bar_interval == "1h"
        import json
        assert json.loads(a.bar_evidence)["chosen_session"] == "all"

    def test_an_all_session_pass_that_approves_no_session_is_rejected(self, store) -> None:
        row = _all_session_row({s: {"verdict": "avoid", "size_multiplier": 0.0} for s in ("premarket", "regular", "afterhours", "overnight")})
        evidence = {"bars": [row], "passing_bars": ["1h"], "chosen": row, "chosen_bar": "1h", "chosen_session": "all"}
        a = store.get_artifact(write_artifact_from_research_pass(_PASS_CONTENT, strategy_store=store, source_run_id="t3",
                                                                  bar_validator=lambda *x: evidence))
        assert a.status == ArtifactStatus.DISABLED and a.trading_sessions == ""
