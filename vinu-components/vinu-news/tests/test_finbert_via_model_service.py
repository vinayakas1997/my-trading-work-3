"""FinBERT scoring in vinu-news: goes to the model service when VINU_MODEL_SERVICE_URL is set, runs in-process otherwise, and a
service failure is raised, never turned into neutral scores."""

import pytest

from vinu_infra import model_client
from vinu_news.analysis.enrichment import finbert_sentiment as fs


def test_with_the_service_url_the_texts_are_scored_remotely(monkeypatch):
    monkeypatch.setenv("VINU_MODEL_SERVICE_URL", "http://models-api:8096")
    calls = []
    monkeypatch.setattr(model_client, "score_finbert",
                        lambda texts, bs, raw_sink=None: calls.append(texts) or [{"finbert_label": "positive", "finbert_score": 0.7}] * len(texts))
    assert fs.score_finbert_batch(["good news", "more"])[1]["finbert_score"] == 0.7
    assert calls == [["good news", "more"]]
    assert fs.score_finbert("x")["finbert_label"] == "positive"


def test_only_blank_texts_never_call_the_service(monkeypatch):
    monkeypatch.setenv("VINU_MODEL_SERVICE_URL", "http://models-api:8096")
    monkeypatch.setattr(model_client, "score_finbert", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no call")))
    assert fs.score_finbert_batch(["", "  "]) == [{"finbert_label": "neutral", "finbert_score": 0.0}] * 2


def test_a_service_failure_propagates(monkeypatch):
    monkeypatch.setenv("VINU_MODEL_SERVICE_URL", "http://models-api:8096")

    def down(texts, bs, raw_sink=None):
        raise model_client.ModelServiceError("unreachable", reason="unreachable")

    monkeypatch.setattr(model_client, "score_finbert", down)
    with pytest.raises(model_client.ModelServiceError):
        fs.score_finbert_batch(["x"])


def test_without_the_url_the_local_scorer_is_used(monkeypatch):
    monkeypatch.delenv("VINU_MODEL_SERVICE_URL", raising=False)
    import vinu_infra.finbert_scoring as local

    monkeypatch.setattr(local, "score_finbert_batch", lambda texts, bs: [{"finbert_label": "negative", "finbert_score": -0.4}] * len(texts))
    assert fs.score_finbert_batch(["x"]) == [{"finbert_label": "negative", "finbert_score": -0.4}]


def test_importing_the_local_scorer_needs_no_torch_and_blank_texts_skip_the_model():
    from vinu_infra.finbert_scoring import score_finbert_batch

    assert score_finbert_batch(["", " "]) == [{"finbert_label": "neutral", "finbert_score": 0.0}] * 2


# ---- layer C: the shape of the service's answer is recorded against the edge contract

def test_the_service_answer_shape_is_recorded_against_the_contract(monkeypatch, tmp_path):
    from vinu_infra import pipeline_edge_recorder as rec

    monkeypatch.setenv("VINU_MODEL_SERVICE_URL", "http://models-api:8096")
    monkeypatch.delenv("VINU_STRATEGY_EVAL_DATA_ROOT", raising=False)
    monkeypatch.setenv("VINU_EDGE_DATA_ROOT", str(tmp_path))
    rec.reset_for_tests()
    edge = "models.finbert_score->news.backfill"

    def answer(body):
        def fake(texts, bs, raw_sink=None):
            if raw_sink is not None:
                raw_sink.append(body)
            return [{"finbert_label": "positive", "finbert_score": 0.5}] * len(texts)

        monkeypatch.setattr(model_client, "score_finbert", fake)

    answer({"count": 1, "results": [{"finbert_label": "positive", "finbert_score": 0.5}]})
    fs.score_finbert_batch(["good"])
    assert rec.resolve_edge_status_store().get_state(edge)["status"] == "received"
    answer({"count": 1, "results": [{"label": "positive"}]})  # the service renamed its fields
    fs.score_finbert_batch(["good"])
    st = rec.resolve_edge_status_store().get_state(edge)
    assert st["status"] == "malformed" and "finbert_label" in st["last_detail"]
    rec.reset_for_tests()
