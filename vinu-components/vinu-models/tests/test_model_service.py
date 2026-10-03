"""The model-serving service, with fake angle modules (no torch needed): typed errors, no silent fallback, and the GPU slot held
until a timed-out computation really finishes."""

from __future__ import annotations

import importlib.util
import time
import types

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from vinu_models.server.app import create_app
from vinu_models.service import ModelError, ModelService, discover_model_angles

REAL_MODEL_ANGLES = {
    "chronos", "dlinear", "itransformer", "kronos", "lpatchtst", "lstm", "patchtst", "tft", "timer_timerxl", "timesfm",
    "tips_regime_aware_transformer",
}


def _module(fn):
    return types.SimpleNamespace(compute=fn)


def _echo(symbol, bars=None, news=None, from_ts=None, to_ts=None, time_format=None):
    return pd.DataFrame([{"symbol": symbol, "n_bars": len(bars), "n_news": len(news), "tf": time_format,
                          "last_close": float(bars["close"].iloc[-1]) if len(bars) else None}])


def _svc(loader=None, **kw):
    return ModelService(module_loader=loader or (lambda angle: _module(_echo)), models_enabled_fn=lambda: True, **kw)


def _client(svc):
    return TestClient(create_app(svc))


BODY = {"symbol": "AAPL", "bars": [{"bar_ts": 1, "close": 10.0}, {"bar_ts": 2, "close": 11.5}], "news": [{"id": 1}],
        "time_format": "1D"}


def test_discovery_finds_exactly_the_eleven_model_angles_and_none_of_the_others():
    found = set(discover_model_angles())
    assert found == REAL_MODEL_ANGLES
    assert "arima" not in found and "news_price_causality" not in found and "moirai" not in found


def test_compute_runs_the_angle_and_returns_its_rows_with_the_inputs_rebuilt():
    r = _client(_svc()).post("/models/angle/chronos/compute", json=BODY)
    assert r.status_code == 200
    out = r.json()
    assert out["rows"] == [{"symbol": "AAPL", "n_bars": 2, "n_news": 1, "tf": "1D", "last_close": 11.5}]
    assert out["row_count"] == 1 and out["angle"] == "chronos" and "policy_version" in out and out["latency_ms"] >= 0


def test_empty_result_is_an_empty_list_not_an_error():
    svc = _svc(lambda a: _module(lambda **k: pd.DataFrame()))
    out = _client(svc).post("/models/angle/chronos/compute", json=BODY).json()
    assert out["rows"] == [] and out["row_count"] == 0


def test_a_non_model_or_unknown_angle_is_refused_with_404():
    c = _client(_svc())
    for name in ("arima", "does_not_exist", "moirai"):
        r = c.post(f"/models/angle/{name}/compute", json=BODY)
        assert r.status_code == 404 and r.json()["detail"]["reason"] == "unknown_angle"


def test_models_disabled_is_a_503_not_an_empty_result():
    svc = ModelService(module_loader=lambda a: _module(_echo), models_enabled_fn=lambda: False)
    r = _client(svc).post("/models/angle/chronos/compute", json=BODY)
    assert r.status_code == 503 and r.json()["detail"]["reason"] == "models_disabled"


def test_a_missing_library_is_a_503_naming_it():
    def loader(angle):
        raise ImportError("No module named 'torch'")

    r = _client(_svc(loader)).post("/models/angle/kronos/compute", json=BODY)
    assert r.status_code == 503 and r.json()["detail"]["reason"] == "model_unavailable"
    assert "torch" in r.json()["detail"]["message"]


def test_an_exception_inside_the_angle_is_a_500_with_the_error():
    svc = _svc(lambda a: _module(lambda **k: (_ for _ in ()).throw(ValueError("bad window"))))
    r = _client(svc).post("/models/angle/lstm/compute", json=BODY)
    assert r.status_code == 500 and r.json()["detail"]["reason"] == "compute_error" and "bad window" in r.json()["detail"]["message"]


def test_a_non_dataframe_result_is_a_500():
    svc = _svc(lambda a: _module(lambda **k: {"not": "a frame"}))
    r = _client(svc).post("/models/angle/lstm/compute", json=BODY)
    assert r.status_code == 500 and "DataFrame" in r.json()["detail"]["message"]


def test_symbol_is_required():
    r = _client(_svc()).post("/models/angle/chronos/compute", json={"bars": []})
    assert r.status_code == 422


def test_a_timeout_is_a_504_and_the_slot_stays_taken_until_the_work_really_ends():
    import asyncio

    def slow(**k):
        time.sleep(0.4)
        return pd.DataFrame([{"ok": 1}])

    svc = _svc(lambda a: _module(slow), timeout_sec=0.05, max_concurrent=1)

    async def scenario():
        with pytest.raises(ModelError) as info:
            await svc.compute_angle("chronos", BODY)
        assert info.value.status == 504 and info.value.reason == "timeout"
        # the caller gave up, but the worker is still running: no second job may start on the same slot
        assert svc._slots.acquire(blocking=False) is False
        await asyncio.sleep(0.7)
        assert svc._slots.acquire(blocking=False) is True

    asyncio.run(scenario())


def test_the_http_route_maps_a_timeout_to_504():
    def slow(**k):
        time.sleep(0.2)
        return pd.DataFrame([{"ok": 1}])

    r = _client(_svc(lambda a: _module(slow), timeout_sec=0.05)).post("/models/angle/chronos/compute", json=BODY)
    assert r.status_code == 504 and r.json()["detail"]["reason"] == "timeout"


def test_status_and_health():
    c = _client(_svc())
    assert c.get("/models/health").json()["ok"] is True
    st = c.get("/models/status").json()
    assert st["models_enabled"] is True and {a["angle"] for a in st["angles"]} == REAL_MODEL_ANGLES
    assert c.get("/models/angles").json()["angles"] == sorted(REAL_MODEL_ANGLES)


def test_errors_are_counted_in_status():
    svc = _svc(lambda a: _module(lambda **k: (_ for _ in ()).throw(RuntimeError("x"))))
    c = _client(svc)
    c.post("/models/angle/lstm/compute", json=BODY)
    stats = c.get("/models/status").json()["stats"]
    assert stats["errors"] == 1 and "x" in stats["last_error"]


@pytest.mark.skipif(importlib.util.find_spec("torch") is not None, reason="only meaningful without torch")
def test_without_torch_the_deep_status_says_which_angles_are_unavailable_and_why():
    st = ModelService(models_enabled_fn=lambda: True).status(deep=True)
    bad = {a["angle"]: a["reason"] for a in st["angles"] if not a["available"]}
    assert bad and all("torch" in r.lower() or "required library" in r.lower() for r in bad.values())
    assert st["torch_installed"] is False


# ------------------------------------------------------------------ finbert

def test_finbert_scores_through_the_service():
    svc = ModelService(models_enabled_fn=lambda: True,
                       finbert_scorer=lambda texts, bs: [{"finbert_label": "positive", "finbert_score": 0.5}] * len(texts))
    out = _client(svc).post("/models/finbert/score", json={"texts": ["a", "b"]}).json()
    assert out["count"] == 2 and out["results"][0]["finbert_label"] == "positive"


def test_finbert_missing_library_is_a_503_and_disabled_is_a_503():
    def boom(texts, bs):
        raise ImportError("No module named 'transformers'")

    r = _client(ModelService(models_enabled_fn=lambda: True, finbert_scorer=boom)).post("/models/finbert/score", json={"texts": ["a"]})
    assert r.status_code == 503 and r.json()["detail"]["reason"] == "model_unavailable"
    r = _client(ModelService(models_enabled_fn=lambda: False, finbert_scorer=boom)).post("/models/finbert/score", json={"texts": ["a"]})
    assert r.status_code == 503 and r.json()["detail"]["reason"] == "models_disabled"


def test_modelerror_carries_status_and_reason():
    e = ModelError(503, "x", "msg")
    assert (e.status, e.reason, e.message) == (503, "x", "msg")


# ------------------------------------------------------------------ proxy fallback policy

def _proxy_module():
    return _module(lambda **k: pd.DataFrame([{"symbol": k["symbol"], "model_backend": "fallback_proxy", "fallback_reason": "weights missing"}]))


def test_a_proxy_row_is_reported_by_default_and_counted():
    svc = _svc(lambda a: _proxy_module())
    c = _client(svc)
    out = c.post("/models/angle/timesfm/compute", json=BODY).json()
    assert out["backends"] == {"fallback_proxy": 1} and out["rows"][0]["model_backend"] == "fallback_proxy"
    assert c.get("/models/status").json()["stats"]["proxy_rows"] == 1


def test_with_allow_proxy_off_a_proxy_row_is_a_503_not_a_stored_result():
    svc = _svc(lambda a: _proxy_module(), allow_proxy=False)
    r = _client(svc).post("/models/angle/timesfm/compute", json=BODY)
    assert r.status_code == 503 and r.json()["detail"]["reason"] == "model_unavailable"
    assert "weights missing" in r.json()["detail"]["message"]


def test_real_model_rows_are_unaffected_by_allow_proxy_off():
    svc = _svc(lambda a: _module(lambda **k: pd.DataFrame([{"symbol": k["symbol"], "model_backend": "pretrained"}])), allow_proxy=False)
    out = _client(svc).post("/models/angle/chronos/compute", json=BODY).json()
    assert out["backends"] == {"pretrained": 1}
