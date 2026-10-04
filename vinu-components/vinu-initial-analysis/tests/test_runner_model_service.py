"""The analysis runner and the model-serving service: model-category angles go remote when VINU_MODEL_SERVICE_URL is set (without
ever importing the angle, so no torch), everything else stays in-process, and a service failure is a real error run."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from vinu_infra import model_client
from vinu_infra import pipeline_edge_recorder as rec
from vinu_initial_analysis.runner import AngleRunner
from vinu_initial_analysis.storage.meta import RunLog
from vinu_initial_analysis.storage.parquet import AngleStorage


class _Price:
    def get_candles(self, *a, **k):
        return [{"bar_ts": 1, "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1}]


class _LocalMod:
    CALLS = 0

    @classmethod
    def compute(cls, symbol, bars=None, news=None, from_ts=None, to_ts=None, time_format=None):
        cls.CALLS += 1
        return pd.DataFrame([{"symbol": symbol, "where": "local"}])


@pytest.fixture(autouse=True)
def _edges(tmp_path, monkeypatch):
    monkeypatch.delenv("VINU_STRATEGY_EVAL_DATA_ROOT", raising=False)
    monkeypatch.setenv("VINU_EDGE_DATA_ROOT", str(tmp_path / "edges"))
    (tmp_path / "edges").mkdir()
    rec.reset_for_tests()
    yield
    rec.reset_for_tests()


def _runner(tmp_path, category):
    root = tmp_path / "data"
    root.mkdir()
    r = AngleRunner(AngleStorage(str(root)), RunLog(root / "runs.db"), price_client=_Price())
    r._angles = [{"name": "fakemodel", "spec": {"time_formats": ["1D"], "category": category}}]
    _LocalMod.CALLS = 0

    def importer(name):
        return _LocalMod

    r._import_compute = importer
    return r


def _edge():
    s = rec.resolve_edge_status_store()
    return s.get_state("models.angle_compute->initial_analysis.runner") if s else None


def test_a_model_angle_goes_to_the_service_and_is_never_imported_locally(tmp_path, monkeypatch):
    monkeypatch.setenv("VINU_MODEL_SERVICE_URL", "http://models-api:8096")
    seen = {}

    def fake_compute(angle, **kw):
        seen.update(angle=angle, symbol=kw["symbol"], n_bars=len(kw["bars"]), tf=kw["time_format"])
        return pd.DataFrame([{"symbol": kw["symbol"], "where": "service"}])

    monkeypatch.setattr(model_client, "compute_angle", fake_compute)
    r = _runner(tmp_path, "model")
    r._import_compute = lambda name: (_ for _ in ()).throw(AssertionError("must not import a model angle when remote"))
    out = r.run("AAPL", angle_names=["fakemodel"])
    assert out["fakemodel"]["status"] == "completed" and out["fakemodel"]["row_count"] == 1
    assert seen == {"angle": "fakemodel", "symbol": "AAPL", "n_bars": 1, "tf": "1D"}
    assert _edge()["status"] == "received"


def test_a_service_failure_is_an_error_run_that_is_retried_not_a_completed_one(tmp_path, monkeypatch):
    monkeypatch.setenv("VINU_MODEL_SERVICE_URL", "http://models-api:8096")

    def down(angle, **kw):
        raise model_client.ModelServiceError("model service unreachable", reason="unreachable")

    monkeypatch.setattr(model_client, "compute_angle", down)
    r = _runner(tmp_path, "model")
    out = r.run("AAPL", angle_names=["fakemodel"])
    assert out["fakemodel"]["status"] == "error" and "unreachable" in out["fakemodel"]["error"]
    assert not r._run_log.has_existing_run("AAPL", "fakemodel", None, None, granularity="1D")
    assert _edge()["status"] == "missing" and "unreachable" in _edge()["last_detail"]


def test_an_empty_service_result_is_recorded_empty(tmp_path, monkeypatch):
    monkeypatch.setenv("VINU_MODEL_SERVICE_URL", "http://models-api:8096")
    monkeypatch.setattr(model_client, "compute_angle", lambda angle, **kw: pd.DataFrame())
    out = _runner(tmp_path, "model").run("AAPL", angle_names=["fakemodel"])
    assert out["fakemodel"]["row_count"] == 0 and _edge()["status"] == "empty"


def test_a_non_model_angle_stays_local_even_when_the_service_is_configured(tmp_path, monkeypatch):
    monkeypatch.setenv("VINU_MODEL_SERVICE_URL", "http://models-api:8096")
    monkeypatch.setattr(model_client, "compute_angle", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no")))
    out = _runner(tmp_path, "raw_data").run("AAPL", angle_names=["fakemodel"])
    assert out["fakemodel"]["row_count"] == 1 and _LocalMod.CALLS == 1 and _edge() is None


def test_without_the_service_url_a_model_angle_runs_in_process_as_before(tmp_path, monkeypatch):
    monkeypatch.delenv("VINU_MODEL_SERVICE_URL", raising=False)
    out = _runner(tmp_path, "model").run("AAPL", angle_names=["fakemodel"])
    assert out["fakemodel"]["row_count"] == 1 and _LocalMod.CALLS == 1


def test_the_weights_store_can_be_imported_without_torch():
    import importlib.util

    from vinu_initial_analysis.storage import weights

    assert weights.WeightsStore is not None
    if importlib.util.find_spec("torch") is None:
        with pytest.raises(ImportError):
            weights.WeightsStore(Path(".")).load("x/y.pt")


def test_the_service_answer_shape_is_recorded_against_the_contract(tmp_path, monkeypatch):
    """Layer C: a wrong-shaped answer is recorded `malformed`; the run itself is unchanged."""
    monkeypatch.setenv("VINU_MODEL_SERVICE_URL", "http://models-api:8096")

    def answer(body):
        def fake(angle, raw_sink=None, **kw):
            if raw_sink is not None:
                raw_sink.append(body)
            return pd.DataFrame([{"symbol": kw["symbol"]}])

        monkeypatch.setattr(model_client, "compute_angle", fake)

    r = _runner(tmp_path, "model")
    answer({"angle": "fakemodel", "row_count": 1, "rows": [{"symbol": "AAPL"}], "backends": {"chronos": 1}})
    out = r.run("AAPL", angle_names=["fakemodel"])
    assert out["fakemodel"]["status"] == "completed" and _edge()["status"] == "received"
    answer({"angle": "fakemodel", "row_count": 1, "data": [{"symbol": "AAPL"}]})  # `rows` renamed
    out = r.run("MSFT", angle_names=["fakemodel"])
    assert out["fakemodel"]["status"] == "completed"  # recording never changes the run
    assert _edge()["status"] == "malformed" and "rows" in _edge()["last_detail"]
