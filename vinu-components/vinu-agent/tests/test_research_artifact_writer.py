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
