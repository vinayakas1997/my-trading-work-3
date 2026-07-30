from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from fastapi.testclient import TestClient

from vinu_initial_analysis.angles.pnl_attribution.compute import aggregate_pnl_attribution, compute
from vinu_initial_analysis.config import VinuInitialAnalysisConfig
from vinu_initial_analysis.pnl_attribution_ingest import ingest_closed_positions
from vinu_initial_analysis.server.app import create_app
from vinu_initial_analysis.service import InitialAnalysisService
from vinu_initial_analysis.storage.parquet import AngleStorage


def _closed_position(pid: str, realized_pnl: float, avg_entry: float = 100.0, qty: float = 10.0) -> dict:
    return {
        "position_id": pid,
        "symbol": "AAPL",
        "side": "long",
        "qty": qty,
        "avg_entry": avg_entry,
        "realized_pnl": realized_pnl,
        "closed_at": "2026-07-27T00:00:00Z",
        "artifact_id": "art_1",
    }


class TestAggregatePnlAttribution:
    def test_no_data_when_empty(self) -> None:
        df = aggregate_pnl_attribution("AAPL", [])
        assert df.iloc[0]["status"] == "no_data"

    def test_computes_win_rate_and_totals(self) -> None:
        positions = [
            _closed_position("p1", 50.0),   # win, +5%
            _closed_position("p2", -20.0),  # loss, -2%
            _closed_position("p3", 30.0),   # win, +3%
        ]
        df = aggregate_pnl_attribution("AAPL", positions)
        row = df.iloc[0]
        assert row["n_trades"] == 3
        assert row["total_realized_pnl"] == 60.0
        assert row["win_rate"]["mean"] == pytest.approx(2 / 3)
        assert row["win_rate"]["n_observations"] == 3

    def test_avg_win_and_loss_pct(self) -> None:
        positions = [_closed_position("p1", 50.0), _closed_position("p2", -20.0)]
        df = aggregate_pnl_attribution("AAPL", positions)
        row = df.iloc[0]
        assert row["avg_win_pct"]["mean"] == pytest.approx(0.05)
        assert row["avg_loss_pct"]["mean"] == pytest.approx(-0.02)

    def test_zero_cost_position_does_not_crash(self) -> None:
        positions = [_closed_position("p1", 10.0, avg_entry=0.0, qty=0.0)]
        df = aggregate_pnl_attribution("AAPL", positions)
        assert df.iloc[0]["status"] == "ok"

    def test_generic_compute_is_a_documented_no_op(self) -> None:
        df = compute("AAPL")
        assert df.iloc[0]["status"] == "push_fed_not_runner_driven"


class TestIngestClosedPositions:
    def test_first_batch_populates_angle(self) -> None:
        with TemporaryDirectory() as tmp:
            storage = AngleStorage(tmp)
            ingest_closed_positions(storage, "AAPL", [_closed_position("p1", 50.0)])
            df = storage.read_latest("AAPL", "pnl_attribution")
            assert df.iloc[0]["n_trades"] == 1

    def test_second_batch_accumulates_not_replaces(self) -> None:
        with TemporaryDirectory() as tmp:
            storage = AngleStorage(tmp)
            ingest_closed_positions(storage, "AAPL", [_closed_position("p1", 50.0)])
            ingest_closed_positions(storage, "AAPL", [_closed_position("p2", -20.0)])
            df = storage.read_latest("AAPL", "pnl_attribution")
            assert df.iloc[0]["n_trades"] == 2
            assert df.iloc[0]["total_realized_pnl"] == 30.0

    def test_redelivery_of_same_position_id_does_not_double_count(self) -> None:
        with TemporaryDirectory() as tmp:
            storage = AngleStorage(tmp)
            ingest_closed_positions(storage, "AAPL", [_closed_position("p1", 50.0)])
            ingest_closed_positions(storage, "AAPL", [_closed_position("p1", 50.0)])
            df = storage.read_latest("AAPL", "pnl_attribution")
            assert df.iloc[0]["n_trades"] == 1

    def test_symbol_is_uppercased(self) -> None:
        with TemporaryDirectory() as tmp:
            storage = AngleStorage(tmp)
            ingest_closed_positions(storage, "aapl", [_closed_position("p1", 50.0)])
            df = storage.read_latest("AAPL", "pnl_attribution")
            assert df.iloc[0]["n_trades"] == 1


class TestRoutes:
    @pytest.fixture
    def client(self, tmp_path: Path) -> TestClient:
        config = VinuInitialAnalysisConfig(data_root=tmp_path)
        service = InitialAnalysisService(config)
        return TestClient(create_app(service))

    def test_record_endpoint_populates_angle(self, client: TestClient) -> None:
        resp = client.post(
            "/analysis/pnl-attribution/AAPL/record",
            json={"closed_positions": [_closed_position("p1", 50.0)]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["symbol"] == "AAPL"
        assert data["n_recorded"] == 1

        angle_resp = client.get("/analysis/angle/pnl_attribution/AAPL")
        assert angle_resp.status_code == 200
        rows = angle_resp.json()["data"]
        assert rows[-1]["n_trades"] == 1

    def test_run_with_angle_names_does_not_error(self, client: TestClient) -> None:
        resp = client.post("/analysis/run/AAPL", params={"angle_names": "shock_personality,shock_clustering"})
        assert resp.status_code == 200
