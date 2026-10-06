import asyncio
import json

import httpx

from vinu_infra.llm import AsyncLlmClient, LlmConfig
from vinu_infra.llm.identity import current_purpose, llm_identity_headers, purpose_scope


def test_headers_name_the_caller_and_only_add_a_purpose_when_one_is_set():
    assert llm_identity_headers("vinu-research") == {"X-Vinu-Caller": "vinu-research"}
    with purpose_scope("live_decision"):
        assert llm_identity_headers("vinu-agent") == {"X-Vinu-Caller": "vinu-agent", "X-Vinu-Purpose": "live_decision"}
        with purpose_scope("hindsight"):
            assert current_purpose() == "hindsight"
        assert current_purpose() == "live_decision"
    assert current_purpose() is None


def test_async_client_sends_who_is_asking(tmp_path):
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(request.headers)
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"choices": [{"message": {"content": "{\"a\": 1}"}}], "usage": {}})

    cfg = LlmConfig(base_url="http://gw/v1", model="m", data_root=str(tmp_path), ttl_sec=0, max_tokens=123)
    client = AsyncLlmClient(cfg, service="vinu-research", http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))

    async def go():
        with purpose_scope("strategy_writer"):
            out = await client.chat_json("sys", "user")
        await client.close()
        return out

    assert asyncio.run(go()) == {"a": 1}
    assert seen["x-vinu-caller"] == "vinu-research" and seen["x-vinu-purpose"] == "strategy_writer"
    assert seen["body"]["max_tokens"] == 123
