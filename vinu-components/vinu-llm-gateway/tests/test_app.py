import json

import httpx
from fastapi.testclient import TestClient

from vinu_llm_gateway.app import create_app
from vinu_llm_gateway.gateway import Gateway, GatewayConfig

MODELS = {"data": [{"id": "m", "meta": {"n_ctx": 40192}}]}


def _client(tmp_path, handler):
    cfg = GatewayConfig(db_path=str(tmp_path / "g.db"), upstream_url="http://up/v1")
    gw = Gateway(cfg, http=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    return TestClient(create_app(gw))


def test_models_are_passed_through_so_the_agent_can_read_the_context_size(tmp_path):
    seen = []

    def handler(request):
        seen.append(str(request.url))
        return httpx.Response(200, json=MODELS)

    with _client(tmp_path, handler) as c:
        r = c.get("/v1/models")
    assert r.status_code == 200 and r.json()["data"][0]["meta"]["n_ctx"] == 40192
    assert seen == ["http://up/v1/models"]


def test_models_reports_an_unreachable_model_server(tmp_path):
    def handler(request):
        raise httpx.ConnectError("down")

    with _client(tmp_path, handler) as c:
        r = c.get("/v1/models")
    assert r.status_code == 502 and "unreachable" in r.json()["error"]["message"]


def test_chat_over_http_returns_the_openai_reply_and_rejects_a_bad_purpose(tmp_path):
    reply = {"choices": [{"message": {"content": "hi"}}], "usage": {"prompt_tokens": 1, "completion_tokens": 1}}
    with _client(tmp_path, lambda request: httpx.Response(200, json=reply)) as c:
        body = {"model": "m", "messages": [{"role": "user", "content": "x"}], "max_tokens": 5}
        ok = c.post("/v1/chat/completions", json=body, headers={"X-Vinu-Caller": "vinu-research"})
        bad = c.post("/v1/chat/completions", json=body, headers={"X-Vinu-Caller": "vinu-research", "X-Vinu-Purpose": "nope"})
        broken = c.post("/v1/chat/completions", content=b"not json")
        q = c.get("/llm/queue").json()
    assert ok.status_code == 200 and ok.json() == reply
    assert bad.status_code == 400 and "unknown purpose" in bad.json()["error"]["message"]
    assert broken.status_code == 400
    assert q["queue"] == {} and q["history_rows"] == 1
