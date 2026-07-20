from __future__ import annotations

from pathlib import Path

import pytest

from vinu_research.storage import ResearchStorage
from vinu_research.storage.models import ResearchRunRecord


@pytest.fixture
def tmp_db_path(tmp_path: Path) -> Path:
    return tmp_path / "test_research.db"


@pytest.fixture
def storage(tmp_db_path: Path) -> ResearchStorage:
    s = ResearchStorage(tmp_db_path)
    yield s
    s.close()


@pytest.fixture
def sample_record() -> ResearchRunRecord:
    return ResearchRunRecord(
        user_idea="test SMA crossover on AAPL",
        symbol="AAPL",
        from_date="2024-01-01",
        to_date="2024-12-31",
    )


@pytest.fixture
def inserted_run(storage: ResearchStorage, sample_record: ResearchRunRecord) -> ResearchRunRecord:
    return storage.insert_run(sample_record)


@pytest.fixture
def strategy_store(tmp_path: Path):
    from vinu_research.storage.strategy_store import SqliteStrategyStore
    s = SqliteStrategyStore(tmp_path / "test_strategy_store.db")
    yield s
    s.close()


@pytest.fixture
async def service(storage: ResearchStorage, strategy_store, tmp_path: Path):
    from vinu_research.config import ResearchConfig
    cfg = ResearchConfig(
        features_api_url="http://localhost:18000",
        simulator_api_url="http://localhost:18001",
        correlation_api_url="http://localhost:18002",
        data_root=tmp_path,
    )
    from vinu_research.service import ResearchService
    svc = ResearchService(config=cfg, storage=storage, strategy_store=strategy_store)
    yield svc
    await svc.close()
