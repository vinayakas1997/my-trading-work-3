from __future__ import annotations

import pandas as pd
from pathlib import Path
from tempfile import TemporaryDirectory

from vinu_initial_analysis.storage.admin import delete_angle
from vinu_initial_analysis.storage.meta import RunLog
from vinu_initial_analysis.storage.parquet import AngleStorage
from vinu_initial_analysis.storage.weights import WeightsStore


def test_delete_angle_removes_analysis_weights_and_run_log_rows():
    with TemporaryDirectory() as tmp:
        run_log = RunLog(Path(tmp) / "runs.db")
        try:
            storage = AngleStorage(tmp, run_log=run_log)
            weights = WeightsStore(tmp)

            for symbol, run_id in (("AAPL", "r1"), ("MSFT", "r2")):
                storage.write(symbol, "dlinear", pd.DataFrame({"x": [1]}), run_id=run_id)
                run_log.record_run(symbol, "dlinear", run_id)
                weights.save(symbol, "dlinear", "1D", 1715779800, {"w": 1})

            storage.write("AAPL", "arima", pd.DataFrame({"x": [1]}), run_id="r3")
            run_log.record_run("AAPL", "arima", "r3")

            result = delete_angle(tmp, "dlinear", run_log=run_log)

            assert result == {"analysis_dirs": 2, "weights_dirs": 2, "run_log_rows": 2}
            assert not (Path(tmp) / "analysis" / "AAPL" / "dlinear").exists()
            assert not (Path(tmp) / "analysis" / "MSFT" / "dlinear").exists()
            assert not (Path(tmp) / "weights" / "AAPL" / "dlinear").exists()
            assert run_log.get_runs(angle_name="dlinear") == []

            # arima (a different angle) must survive untouched.
            assert (Path(tmp) / "analysis" / "AAPL" / "arima").exists()
            assert len(run_log.get_runs(angle_name="arima")) == 1
        finally:
            run_log.close()


def test_delete_angle_without_run_log_still_removes_files():
    with TemporaryDirectory() as tmp:
        storage = AngleStorage(tmp)
        storage.write("AAPL", "dlinear", pd.DataFrame({"x": [1]}), run_id="r1")

        result = delete_angle(tmp, "dlinear")

        assert result["analysis_dirs"] == 1
        assert result["run_log_rows"] == 0
        assert not (Path(tmp) / "analysis" / "AAPL" / "dlinear").exists()


def test_delete_angle_is_a_no_op_when_nothing_stored():
    with TemporaryDirectory() as tmp:
        result = delete_angle(tmp, "never_written")
        assert result == {"analysis_dirs": 0, "weights_dirs": 0, "run_log_rows": 0}
