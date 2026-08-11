"""Tests for SqliteStrategyStore's narrow status-transition methods.

Pillar 1/6's "narrow wrapper per transition, no generic update" hardening,
made real -- see New-talk-agents/new-thinking/agentic-architectural-planning/
planning-implementation/02-pillar6-immutability-and-deletion-policy.md.
"""

from __future__ import annotations

import pytest

from vinu_research.models import Artifact, ArtifactStatus
from vinu_research.storage.strategy_store import InvalidStatusTransition, SqliteStrategyStore


@pytest.fixture
def artifact(strategy_store: SqliteStrategyStore) -> Artifact:
    a = Artifact.create("strategy", "AAPL-test")
    return strategy_store.upsert_artifact(a)


class TestValidTransitions:
    def test_created_to_benching(self, strategy_store: SqliteStrategyStore, artifact: Artifact) -> None:
        updated = strategy_store.mark_benching(artifact.artifact_id)
        assert updated.status == ArtifactStatus.BENCHING
        assert strategy_store.get_artifact(artifact.artifact_id).status == ArtifactStatus.BENCHING

    def test_benching_to_active(self, strategy_store: SqliteStrategyStore, artifact: Artifact) -> None:
        strategy_store.mark_benching(artifact.artifact_id)
        updated = strategy_store.mark_active(artifact.artifact_id)
        assert updated.status == ArtifactStatus.ACTIVE

    def test_active_to_monitoring(self, strategy_store: SqliteStrategyStore, artifact: Artifact) -> None:
        strategy_store.mark_benching(artifact.artifact_id)
        strategy_store.mark_active(artifact.artifact_id)
        updated = strategy_store.mark_monitoring(artifact.artifact_id)
        assert updated.status == ArtifactStatus.MONITORING

    def test_monitoring_back_to_active(self, strategy_store: SqliteStrategyStore, artifact: Artifact) -> None:
        strategy_store.mark_benching(artifact.artifact_id)
        strategy_store.mark_active(artifact.artifact_id)
        strategy_store.mark_monitoring(artifact.artifact_id)
        updated = strategy_store.mark_active(artifact.artifact_id)
        assert updated.status == ArtifactStatus.ACTIVE

    def test_monitoring_to_decayed(self, strategy_store: SqliteStrategyStore, artifact: Artifact) -> None:
        strategy_store.mark_benching(artifact.artifact_id)
        strategy_store.mark_active(artifact.artifact_id)
        strategy_store.mark_monitoring(artifact.artifact_id)
        updated = strategy_store.mark_decayed(artifact.artifact_id)
        assert updated.status == ArtifactStatus.DECAYED

    def test_disabled_reachable_from_any_non_terminal_status(
        self, strategy_store: SqliteStrategyStore, artifact: Artifact
    ) -> None:
        updated = strategy_store.mark_disabled(artifact.artifact_id)
        assert updated.status == ArtifactStatus.DISABLED

    def test_transition_to_current_status_is_a_noop(
        self, strategy_store: SqliteStrategyStore, artifact: Artifact
    ) -> None:
        updated = strategy_store.transition_status(artifact.artifact_id, ArtifactStatus.CREATED)
        assert updated.status == ArtifactStatus.CREATED

    def test_benching_to_pend_via_mark_pend(
        self, strategy_store: SqliteStrategyStore, artifact: Artifact
    ) -> None:
        strategy_store.mark_benching(artifact.artifact_id)
        updated = strategy_store.mark_pend(artifact.artifact_id, approved_size=15000.0)
        assert updated.status == ArtifactStatus.PEND
        assert updated.approved_size == 15000.0
        assert strategy_store.get_artifact(artifact.artifact_id).approved_size == 15000.0

    def test_pend_to_active_via_mark_active(
        self, strategy_store: SqliteStrategyStore, artifact: Artifact
    ) -> None:
        strategy_store.mark_benching(artifact.artifact_id)
        strategy_store.mark_pend(artifact.artifact_id, approved_size=10000.0)
        updated = strategy_store.mark_active(artifact.artifact_id)
        assert updated.status == ArtifactStatus.ACTIVE
        assert updated.approved_size == 10000.0  # preserved through the PEND->ACTIVE move

    def test_benching_to_active_direct_still_works(
        self, strategy_store: SqliteStrategyStore, artifact: Artifact
    ) -> None:
        """ShadowEvaluator's own BENCHING->ACTIVE promotion path (vinu-live,
        independent of risk_gatekeeper_hook.py) must stay valid -- Phase 2
        adds PEND as a new option, it doesn't remove the direct path."""
        strategy_store.mark_benching(artifact.artifact_id)
        updated = strategy_store.mark_active(artifact.artifact_id)
        assert updated.status == ArtifactStatus.ACTIVE

    def test_monitoring_to_pend(self, strategy_store: SqliteStrategyStore, artifact: Artifact) -> None:
        strategy_store.mark_benching(artifact.artifact_id)
        strategy_store.mark_active(artifact.artifact_id)
        strategy_store.mark_monitoring(artifact.artifact_id)
        updated = strategy_store.mark_pend(artifact.artifact_id, approved_size=5000.0)
        assert updated.status == ArtifactStatus.PEND

    def test_mark_pend_idempotent_updates_approved_size(
        self, strategy_store: SqliteStrategyStore, artifact: Artifact
    ) -> None:
        strategy_store.mark_benching(artifact.artifact_id)
        strategy_store.mark_pend(artifact.artifact_id, approved_size=1000.0)
        updated = strategy_store.mark_pend(artifact.artifact_id, approved_size=2000.0)
        assert updated.status == ArtifactStatus.PEND
        assert updated.approved_size == 2000.0

    def test_pend_to_disabled(self, strategy_store: SqliteStrategyStore, artifact: Artifact) -> None:
        strategy_store.mark_benching(artifact.artifact_id)
        strategy_store.mark_pend(artifact.artifact_id, approved_size=1000.0)
        updated = strategy_store.mark_disabled(artifact.artifact_id)
        assert updated.status == ArtifactStatus.DISABLED

    def test_pend_to_pendblock_preserves_approved_size(
        self, strategy_store: SqliteStrategyStore, artifact: Artifact
    ) -> None:
        strategy_store.mark_benching(artifact.artifact_id)
        strategy_store.mark_pend(artifact.artifact_id, approved_size=12000.0)
        updated = strategy_store.mark_pendblock(artifact.artifact_id)
        assert updated.status == ArtifactStatus.PENDBLOCK
        assert updated.approved_size == 12000.0

    def test_pendblock_back_to_pend(self, strategy_store: SqliteStrategyStore, artifact: Artifact) -> None:
        strategy_store.mark_benching(artifact.artifact_id)
        strategy_store.mark_pend(artifact.artifact_id, approved_size=12000.0)
        strategy_store.mark_pendblock(artifact.artifact_id)
        updated = strategy_store.transition_status(artifact.artifact_id, ArtifactStatus.PEND)
        assert updated.status == ArtifactStatus.PEND
        assert updated.approved_size == 12000.0

    def test_pendblock_to_active_on_retry(
        self, strategy_store: SqliteStrategyStore, artifact: Artifact
    ) -> None:
        strategy_store.mark_benching(artifact.artifact_id)
        strategy_store.mark_pend(artifact.artifact_id, approved_size=12000.0)
        strategy_store.mark_pendblock(artifact.artifact_id)
        updated = strategy_store.mark_active(artifact.artifact_id)
        assert updated.status == ArtifactStatus.ACTIVE
        assert updated.approved_size == 12000.0

    def test_pendblock_to_disabled(self, strategy_store: SqliteStrategyStore, artifact: Artifact) -> None:
        strategy_store.mark_benching(artifact.artifact_id)
        strategy_store.mark_pend(artifact.artifact_id, approved_size=1000.0)
        strategy_store.mark_pendblock(artifact.artifact_id)
        updated = strategy_store.mark_disabled(artifact.artifact_id)
        assert updated.status == ArtifactStatus.DISABLED


class TestInvalidTransitions:
    def test_created_to_active_skips_benching(
        self, strategy_store: SqliteStrategyStore, artifact: Artifact
    ) -> None:
        with pytest.raises(InvalidStatusTransition):
            strategy_store.mark_active(artifact.artifact_id)

    def test_disabled_is_terminal(self, strategy_store: SqliteStrategyStore, artifact: Artifact) -> None:
        strategy_store.mark_disabled(artifact.artifact_id)
        with pytest.raises(InvalidStatusTransition):
            strategy_store.mark_benching(artifact.artifact_id)

    def test_decayed_cannot_go_back_to_active(
        self, strategy_store: SqliteStrategyStore, artifact: Artifact
    ) -> None:
        strategy_store.mark_benching(artifact.artifact_id)
        strategy_store.mark_active(artifact.artifact_id)
        strategy_store.mark_monitoring(artifact.artifact_id)
        strategy_store.mark_decayed(artifact.artifact_id)
        with pytest.raises(InvalidStatusTransition):
            strategy_store.mark_active(artifact.artifact_id)

    def test_unknown_artifact_id_raises(self, strategy_store: SqliteStrategyStore) -> None:
        with pytest.raises(InvalidStatusTransition):
            strategy_store.mark_active("art_nonexistent")

    def test_created_to_pend_skips_benching(
        self, strategy_store: SqliteStrategyStore, artifact: Artifact
    ) -> None:
        with pytest.raises(InvalidStatusTransition):
            strategy_store.mark_pend(artifact.artifact_id, approved_size=1.0)

    def test_mark_pend_unknown_artifact_id_raises(self, strategy_store: SqliteStrategyStore) -> None:
        with pytest.raises(InvalidStatusTransition):
            strategy_store.mark_pend("art_nonexistent", approved_size=1.0)

    def test_benching_to_pendblock_skips_pend(
        self, strategy_store: SqliteStrategyStore, artifact: Artifact
    ) -> None:
        strategy_store.mark_benching(artifact.artifact_id)
        with pytest.raises(InvalidStatusTransition):
            strategy_store.mark_pendblock(artifact.artifact_id)
