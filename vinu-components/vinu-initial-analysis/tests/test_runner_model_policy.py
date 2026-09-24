from __future__ import annotations

import importlib
import shutil
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from vinu_infra import model_policy as model_policy_module
from vinu_initial_analysis.runner import ANGLES_DIR, AngleRunner
from vinu_initial_analysis.storage.meta import RunLog
from vinu_initial_analysis.storage.parquet import AngleStorage

_MODEL_ANGLE = "zzz_test_fake_model_angle"

_FAKE_COMPUTE = '''
import pandas as pd

CALLS = []

def compute(symbol, bars=None, news=None, from_ts=None, to_ts=None, time_format=None):
    CALLS.append(time_format)
    return pd.DataFrame([{"symbol": symbol, "time_format": time_format, "status": "ok"}])
'''

_FAKE_MODEL_SPEC = """
title: Fake Model-Category Angle
category: model
time_formats:
- 1D
"""


@pytest.fixture
def fake_model_angle():
    """A real, temporary angle tagged `category: model` -- proves
    AngleRunner.run() actually skips it when VINU_MODELS_ENABLED=false,
    per Decision 4/5 of missing-pieces-of-system/new-theory-of-trading/
    01-planning.md. Same install-under-ANGLES_DIR pattern as
    test_runner_time_format.py's fake_angle fixture, since
    AngleRunner._import_compute() uses a fixed import path, not the
    discovered directory."""
    angle_dir = ANGLES_DIR / _MODEL_ANGLE
    angle_dir.mkdir()
    (angle_dir / "compute.py").write_text(_FAKE_COMPUTE)
    (angle_dir / "spec.yaml").write_text(_FAKE_MODEL_SPEC)
    module_path = f"vinu_initial_analysis.angles.{_MODEL_ANGLE}.compute"
    try:
        yield _MODEL_ANGLE
    finally:
        sys.modules.pop(module_path, None)
        sys.modules.pop(f"vinu_initial_analysis.angles.{_MODEL_ANGLE}", None)
        shutil.rmtree(angle_dir, ignore_errors=True)


def _make_runner(tmp: str) -> tuple[AngleRunner, AngleStorage, RunLog]:
    storage = AngleStorage(tmp)
    run_log = RunLog(Path(tmp) / "runs.db")
    angle_runner = AngleRunner(storage, run_log)
    return angle_runner, storage, run_log


def test_model_angle_runs_when_models_enabled(fake_model_angle, monkeypatch):
    monkeypatch.delenv("VINU_MODELS_ENABLED", raising=False)
    importlib.reload(model_policy_module)
    with TemporaryDirectory() as tmp:
        angle_runner, _, _ = _make_runner(tmp)
        result = angle_runner.run("AAPL", angle_names=[fake_model_angle])
        assert fake_model_angle in result
        assert result[fake_model_angle]["status"] == "completed"


def test_model_angle_skipped_when_models_disabled(fake_model_angle, monkeypatch):
    monkeypatch.setenv("VINU_MODELS_ENABLED", "false")
    importlib.reload(model_policy_module)
    try:
        with TemporaryDirectory() as tmp:
            angle_runner, _, _ = _make_runner(tmp)
            result = angle_runner.run("AAPL", angle_names=[fake_model_angle])
            # Explicitly naming a model-category angle in angle_names can't
            # force it to run while the global switch is off -- Decision 4's
            # policy is applied before the caller's own filter, not instead
            # of it.
            assert fake_model_angle not in result
    finally:
        monkeypatch.delenv("VINU_MODELS_ENABLED", raising=False)
        importlib.reload(model_policy_module)


def test_permanently_disabled_angle_name_never_runs_even_if_named(monkeypatch):
    monkeypatch.delenv("VINU_MODELS_ENABLED", raising=False)
    importlib.reload(model_policy_module)
    with TemporaryDirectory() as tmp:
        angle_runner, _, _ = _make_runner(tmp)
        # moirai is a real, already-discovered angle (permanently excluded
        # per Decision 5) -- naming it explicitly must still produce no
        # result, regardless of its own spec.yaml's category tag.
        result = angle_runner.run("AAPL", angle_names=["moirai"])
        assert "moirai" not in result
