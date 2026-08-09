from __future__ import annotations

import shutil
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from vinu_initial_analysis.runner import ANGLES_DIR, AngleRunner
from vinu_initial_analysis.storage.meta import RunLog
from vinu_initial_analysis.storage.parquet import AngleStorage

_ANGLE_NAME = "zzz_test_fake_multi_tf_angle"

_FAKE_COMPUTE = '''
import pandas as pd

CALLS = []

def compute(symbol, bars=None, news=None, from_ts=None, to_ts=None, time_format=None):
    CALLS.append(time_format)
    return pd.DataFrame([{"symbol": symbol, "time_format": time_format, "status": "ok"}])
'''

_FAKE_SPEC = """
title: Fake Multi-Timeframe Angle
time_formats:
- 1D
- 1H
"""


@pytest.fixture
def fake_angle():
    """Installs a real, temporary angle package under the actual angles/
    directory -- AngleRunner._import_compute() uses a fixed
    `vinu_initial_analysis.angles.{name}.compute` import path, not the
    discovered directory, so this can't be faked with monkeypatch alone.
    """
    angle_dir = ANGLES_DIR / _ANGLE_NAME
    angle_dir.mkdir()
    (angle_dir / "compute.py").write_text(_FAKE_COMPUTE)
    (angle_dir / "spec.yaml").write_text(_FAKE_SPEC)
    module_path = f"vinu_initial_analysis.angles.{_ANGLE_NAME}.compute"
    try:
        yield _ANGLE_NAME
    finally:
        sys.modules.pop(module_path, None)
        sys.modules.pop(f"vinu_initial_analysis.angles.{_ANGLE_NAME}", None)
        shutil.rmtree(angle_dir, ignore_errors=True)


def _make_runner(tmp: str) -> tuple[AngleRunner, AngleStorage, RunLog]:
    storage = AngleStorage(tmp)
    run_log = RunLog(Path(tmp) / "runs.db")
    angle_runner = AngleRunner(storage, run_log)
    return angle_runner, storage, run_log


def test_time_format_none_runs_every_declared_format(fake_angle):
    with TemporaryDirectory() as tmp:
        angle_runner, storage, run_log = _make_runner(tmp)
        try:
            result = angle_runner.run("AAPL", angle_names=[fake_angle])
            assert result[fake_angle]["status"] == "completed"
            assert result[fake_angle]["row_count"] == 2  # one row per declared format (1D + 1H)
            # default (no time_format) writes/records under the storage default "1D"
            back = storage.read_latest("AAPL", fake_angle, granularity="1D")
            assert len(back) == 2
        finally:
            run_log.close()


def test_time_format_restricts_to_one_and_writes_under_its_granularity(fake_angle):
    with TemporaryDirectory() as tmp:
        angle_runner, storage, run_log = _make_runner(tmp)
        try:
            result = angle_runner.run("AAPL", angle_names=[fake_angle], time_format="1H")
            assert result[fake_angle]["row_count"] == 1

            # written under granularity="1H", not the default "1D"
            back_1h = storage.read_latest("AAPL", fake_angle, granularity="1H")
            assert len(back_1h) == 1
            assert back_1h.iloc[0]["time_format"] == "1H"

            # nothing landed under "1D" from this restricted run
            back_1d = storage.read_latest("AAPL", fake_angle, granularity="1D")
            assert len(back_1d) == 0

            # RunLog resolves the latest run scoped to "1H" correctly
            latest = run_log.get_latest_run("AAPL", fake_angle, granularity="1H")
            assert latest is not None
        finally:
            run_log.close()


def test_time_format_not_declared_is_reported_as_error(fake_angle):
    with TemporaryDirectory() as tmp:
        angle_runner, storage, run_log = _make_runner(tmp)
        try:
            result = angle_runner.run("AAPL", angle_names=[fake_angle], time_format="4H")
            # run() catches per-angle exceptions and reports them, doesn't raise
            assert result[fake_angle]["status"] == "error"
            assert "4H" in result[fake_angle]["error"]
        finally:
            run_log.close()


def test_time_format_restricted_run_only_computes_that_one_format(fake_angle):
    with TemporaryDirectory() as tmp:
        angle_runner, storage, run_log = _make_runner(tmp)
        try:
            module = angle_runner._import_compute(fake_angle)
            module.CALLS.clear()
            angle_runner.run("AAPL", angle_names=[fake_angle], time_format="1H")
            assert module.CALLS == ["1H"]  # not ["1D", "1H"] -- 1D was never computed
        finally:
            run_log.close()
