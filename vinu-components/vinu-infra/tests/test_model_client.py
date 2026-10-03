"""The model-service client: success returns real data; every failure raises ModelServiceError with a reason (never an empty or
proxy result)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
import requests

from vinu_infra import model_client
from vinu_infra.model_client import ModelServiceError


@pytest.fixture(autouse=True)
def _url(monkeypatch):
    monkeypatch.setenv("VINU_MODEL_SERVICE_URL", "http://models-api:8096/")
    monkeypatch.delenv("VINU_API_KEY", raising=False)


def _resp(status=200, body=None, text=""):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = body if body is not None else {}
    r.text = text
    return r


def _call(**kw):
    return model_client.compute_angle(
        "chronos", symbol="AAPL", bars=pd.DataFrame({"bar_ts": [1, 2], "close": [1.0, 2.0]}), news=[{"id": 1}],
        from_ts=1, to_ts=2, time_format="1D", **kw)


def test_service_url_is_none_when_unset_and_trims_the_trailing_slash(monkeypatch):
    assert model_client.service_url() == "http://models-api:8096"
    monkeypatch.delenv("VINU_MODEL_SERVICE_URL")
    assert model_client.service_url() is None
    monkeypatch.setenv("VINU_MODEL_SERVICE_URL", "  ")
    assert model_client.service_url() is None


def test_compute_angle_posts_the_inputs_and_returns_the_rows_as_a_frame():
    with patch("requests.post", return_value=_resp(200, {"rows": [{"a": 1}, {"a": 2}]})) as post:
        df = _call()
    assert list(df["a"]) == [1, 2]
    url = post.call_args.args[0]
    assert url == "http://models-api:8096/models/angle/chronos/compute"
    sent = post.call_args.kwargs["data"]
    assert '"symbol": "AAPL"' in sent and '"bar_ts": 1' in sent and '"news": [{"id": 1}]' in sent


def test_an_unreachable_service_raises_with_reason_unreachable():
    with patch("requests.post", side_effect=requests.ConnectionError("refused")):
        with pytest.raises(ModelServiceError) as e:
            _call()
    assert e.value.reason == "unreachable" and "refused" in str(e.value)


def test_a_timeout_raises_with_reason_timeout():
    with patch("requests.post", side_effect=requests.Timeout("slow")):
        with pytest.raises(ModelServiceError) as e:
            _call()
    assert e.value.reason == "timeout"


def test_a_503_carries_the_services_reason_and_status():
    body = {"detail": {"reason": "model_unavailable", "message": "kronos: torch missing"}}
    with patch("requests.post", return_value=_resp(503, body)):
        with pytest.raises(ModelServiceError) as e:
            _call()
    assert e.value.status == 503 and e.value.reason == "model_unavailable" and "torch missing" in str(e.value)


def test_a_response_without_rows_is_a_bad_response():
    with patch("requests.post", return_value=_resp(200, {"oops": 1})):
        with pytest.raises(ModelServiceError) as e:
            _call()
    assert e.value.reason == "bad_response"


def test_not_configured_raises(monkeypatch):
    monkeypatch.delenv("VINU_MODEL_SERVICE_URL")
    with pytest.raises(ModelServiceError) as e:
        _call()
    assert e.value.reason == "not_configured"


def test_the_internal_auth_header_is_sent_when_a_key_is_set(monkeypatch):
    import vinu_infra.auth as auth

    monkeypatch.setattr(auth, "VINU_API_KEY", "k123")
    with patch("requests.post", return_value=_resp(200, {"rows": []})) as post:
        _call()
    assert post.call_args.kwargs["headers"]["Authorization"] == "Bearer k123"


def test_finbert_round_trip_and_length_check():
    with patch("requests.post", return_value=_resp(200, {"results": [{"finbert_score": 0.1, "finbert_label": "positive"}] * 2})):
        assert len(model_client.score_finbert(["a", "b"])) == 2
    with patch("requests.post", return_value=_resp(200, {"results": [{"finbert_score": 0.1}]})):
        with pytest.raises(ModelServiceError):
            model_client.score_finbert(["a", "b"])
