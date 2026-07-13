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
async def service(storage: ResearchStorage):
    from vinu_research.config import ResearchConfig
    cfg = ResearchConfig(
        features_api_url="http://localhost:18000",
        simulator_api_url="http://localhost:18001",
        correlation_api_url="http://localhost:18002",
    )
    from vinu_research.service import ResearchService
    svc = ResearchService(config=cfg, storage=storage)
    yield svc
    await svc.close()
