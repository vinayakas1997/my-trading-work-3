"""Integration test: approve_run flow with correlation gate.

Verifies that:
1. Approve creates artifact with ACTIVE status when gate is disabled (default)
2. Approve creates artifact with ACTIVE status when gate passes
3. Approve creates artifact with BENCHING status when gate blocks
4. The artifact contents are correct in all cases
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, Mock, patch
import tempfile

import pytest

from vinu_research.config import ResearchConfig
from vinu_research.models import ArtifactStatus
from vinu_research.service import ResearchService
from vinu_research.storage.sqlite_backend import ResearchStorage
from vinu_research.storage.strategy_store import SqliteStrategyStore


@pytest.fixture
def config() -> ResearchConfig:
    return ResearchConfig(
        promotion_deflated_sharpe_threshold=0.0,
        promotion_holdout_required=False,
        promotion_stress_test_required=False,
        promotion_correlation_threshold=0.85,
        promotion_correlation_required=True,
    )


@pytest.fixture
def storage() -> ResearchStorage:
    p = Path(tempfile.mktemp(suffix=".db"))
    s = ResearchStorage(p)
    yield s
    s.close()


@pytest.fixture
def strategy_store() -> SqliteStrategyStore:
    p = Path(tempfile.mktemp(suffix=".db"))
    s = SqliteStrategyStore(p)
    yield s
    s.close()


@pytest.fixture
def service(config: ResearchConfig, storage: ResearchStorage, strategy_store: SqliteStrategyStore) -> ResearchService:
    return ResearchService(config=config, storage=storage, strategy_store=strategy_store)


def _finish_run(storage: ResearchStorage, symbol: str = "AAPL") -> int:
    from vinu_research.storage.models import ResearchRunRecord, STATUS_DONE
    record = ResearchRunRecord(
        user_idea="test",
        symbol=symbol,
        from_date="2024-01-01",
        to_date="2024-06-01",
        status=STATUS_DONE,
        strategy_code="def generate_weights(data):\n    return 0",
        best_sharpe=1.5,
        best_max_dd=-0.15,
        deflated_sharpe=0.96,
        holdout_passed=True,
        stress_test_passed=True,
    )
    record = storage.insert_run(record)
    return record.id  # type: ignore[return-value]


def _add_active_strategy(strategy_store: SqliteStrategyStore, symbol: str = "AAPL") -> None:
    from vinu_research.models import Artifact
    art = Artifact.create(type_="strategy", name=f"{symbol}_existing", universe=[symbol])
    art.status = ArtifactStatus.ACTIVE
    art.strategy_code = "def generate_weights(data):\n    return 1"
    art.deflated_sharpe = 0.96
    art.holdout_passed = True
    art.stress_test_passed = True
    strategy_store.upsert_artifact(art)


def _mock_verdict(eligible: bool, avg_corr: float, max_corr: float, n: int = 1) -> Mock:
    v = Mock()
    v.eligible = eligible
    v.avg_correlation = avg_corr
    v.max_correlation = max_corr
    v.n_active = n
    v.correlations = {"a": avg_corr}
    v.reasons = [f"avg correlation {avg_corr:.3f} exceeds threshold 0.85"] if not eligible else ["within threshold"]
    return v


class TestPromotionIntegration:
    @pytest.mark.asyncio
    async def test_approve_creates_active_when_gate_disabled(self, storage: ResearchStorage, strategy_store: SqliteStrategyStore) -> None:
        cfg = ResearchConfig(promotion_correlation_required=False)
        svc = ResearchService(config=cfg, storage=storage, strategy_store=strategy_store)
        _add_active_strategy(strategy_store)
        run_id = _finish_run(storage)

        result = await svc.approve_run(run_id)
        assert result is not None
        assert "artifact_id" in result
        artifacts = strategy_store.list_artifacts_by_statuses([ArtifactStatus.ACTIVE], "strategy")
        assert len(artifacts) == 2

    @pytest.mark.asyncio
    async def test_approve_creates_active_when_gate_passes(self, service: ResearchService, strategy_store: SqliteStrategyStore, storage: ResearchStorage) -> None:
        _add_active_strategy(strategy_store)
        run_id = _finish_run(storage)

        with patch(
            "vinu_research.service.check_correlation_gate",
            new=AsyncMock(return_value=_mock_verdict(eligible=True, avg_corr=0.3, max_corr=0.4)),
        ):
            result = await service.approve_run(run_id)
        assert result is not None
        assert "artifact_id" in result
        artifacts = strategy_store.list_artifacts_by_statuses([ArtifactStatus.ACTIVE], "strategy")
        assert len(artifacts) == 2

    @pytest.mark.asyncio
    async def test_approve_creates_benching_when_gate_blocks(self, service: ResearchService, strategy_store: SqliteStrategyStore, storage: ResearchStorage) -> None:
        _add_active_strategy(strategy_store)
        run_id = _finish_run(storage)

        with patch(
            "vinu_research.service.check_correlation_gate",
            new=AsyncMock(return_value=_mock_verdict(eligible=False, avg_corr=0.95, max_corr=0.96)),
        ):
            result = await service.approve_run(run_id)
        assert result is not None
        assert "artifact_id" in result
        benching = strategy_store.list_artifacts_by_statuses([ArtifactStatus.BENCHING], "strategy")
        assert len(benching) == 1
        active = strategy_store.list_artifacts_by_statuses([ArtifactStatus.ACTIVE], "strategy")
        assert len(active) == 1

    @pytest.mark.asyncio
    async def test_approve_no_active_strategies_still_activates(self, service: ResearchService, strategy_store: SqliteStrategyStore, storage: ResearchStorage) -> None:
        run_id = _finish_run(storage)
        result = await service.approve_run(run_id)
        assert result is not None
        assert "artifact_id" in result
        active = strategy_store.list_artifacts_by_statuses([ArtifactStatus.ACTIVE], "strategy")
        assert len(active) == 1

    @pytest.mark.asyncio
    async def test_approve_preserves_artifact_contents(self, service: ResearchService, strategy_store: SqliteStrategyStore, storage: ResearchStorage) -> None:
        run_id = _finish_run(storage)
        result = await service.approve_run(run_id)
        assert result is not None
        artifact_id = result["artifact_id"]
        art = strategy_store.get_artifact(artifact_id)
        assert art is not None
        assert art.strategy_code == "def generate_weights(data):\n    return 0"
        assert art.source_run_id == run_id
        assert art.initial_sharpe == 1.5
        assert art.deflated_sharpe == 0.96
        assert art.holdout_passed is True
        assert art.stress_test_passed is True
