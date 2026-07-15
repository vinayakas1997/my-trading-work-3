from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path

from vinu_simulator.engine.run_card import write_run_card


class TestWriteRunCard:
    def test_writes_json_and_md_files(self):
        tmp = Path(tempfile.mkdtemp())
        run_card = write_run_card(
            run_dir=tmp,
            run_id="test_001",
            config={
                "symbols": ["AAPL", "MSFT"],
                "start_date": "2024-01-01",
                "end_date": "2024-12-31",
                "interval": "1d",
                "initial_capital": 100000.0,
            },
            metrics={"sharpe_ratio": 1.23, "total_return": 0.15, "max_drawdown": -0.08},
            benchmark_metrics={"SPY": {"sharpe_ratio": 0.5, "total_return": 0.05}},
            trade_count=50,
            equity_points=252,
        )
        assert (tmp / "run_card.json").exists()
        assert (tmp / "run_card.md").exists()

        data = json.loads((tmp / "run_card.json").read_text(encoding="utf-8"))
        assert data["schema_version"] == "0.1"
        assert data["run_id"] == "test_001"
        assert data["metrics"]["sharpe_ratio"] == 1.23
        assert data["trade_count"] == 50
        assert "SPY" in data["benchmark_metrics"]

    def test_includes_artifact_hashes(self):
        tmp = Path(tempfile.mkdtemp())
        (tmp / "equity.parquet").write_bytes(b"fake_parquet_data")
        (tmp / "meta.json").write_text('{"test": true}')

        run_card = write_run_card(
            run_dir=tmp,
            run_id="test_002",
            config={},
            metrics={"sharpe_ratio": 1.0},
        )
        assert len(run_card["artifacts"]) == 2
        for a in run_card["artifacts"]:
            assert "sha256" in a
            assert "size_bytes" in a
            assert a["size_bytes"] > 0

    def test_sha256_is_deterministic(self):
        tmp = Path(tempfile.mkdtemp())
        (tmp / "config.json").write_text('{"test": true}')

        write_run_card(
            run_dir=tmp,
            run_id="test_003",
            config={},
            metrics={"sharpe_ratio": 1.0},
        )
        card = json.loads((tmp / "run_card.json").read_text())
        h1 = card["reproducibility"]["config_hash"]

        actual_hash = hashlib.sha256(b'{"test": true}').hexdigest()
        assert h1 == actual_hash

    def test_markdown_contains_metrics(self):
        tmp = Path(tempfile.mkdtemp())
        write_run_card(
            run_dir=tmp,
            run_id="test_004",
            config={
                "symbols": ["AAPL"],
                "start_date": "2024-01-01",
                "end_date": "2024-12-31",
            },
            metrics={"sharpe_ratio": 2.5, "total_return": 0.3},
        )
        md = (tmp / "run_card.md").read_text(encoding="utf-8")
        assert "test_004" in md
        assert "2.5000" in md
        assert "30.0000%" in md or "0.3000" in md

    def test_empty_config_does_not_crash(self):
        tmp = Path(tempfile.mkdtemp())
        run_card = write_run_card(
            run_dir=tmp,
            run_id="test_005",
            config={},
            metrics={},
        )
        assert run_card["run_id"] == "test_005"

    def test_validation_and_attribution_included(self):
        tmp = Path(tempfile.mkdtemp())
        run_card = write_run_card(
            run_dir=tmp,
            run_id="test_006",
            config={},
            metrics={"sharpe_ratio": 1.0},
            validation={"monte_carlo_p_value": 0.03, "bootstrap_ci": [0.5, 1.5]},
            attribution={"by_symbol": {"AAPL": {"win_rate": 0.6}}},
        )
        assert run_card["validation"]["monte_carlo_p_value"] == 0.03
        assert run_card["attribution"]["by_symbol"]["AAPL"]["win_rate"] == 0.6
