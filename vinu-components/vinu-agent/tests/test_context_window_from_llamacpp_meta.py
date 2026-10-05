"""llama.cpp's /v1/models nests the live context size at data[0].meta.n_ctx. The resolver only looked at the top level, so
the local 40192-token model resolved to the 8000 fallback and the agent loop compacted its memory at 8K tokens: the
research team forgot what it had fetched and re-fetched it for 2.5 hours without reaching a backtest."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from vinu_agent.agent.llm import resolve_context_window

LLAMACPP_MODELS = {
    "models": [{"name": "/models/Qwen3.5-9B-Q4_K_M.gguf"}],
    "object": "list",
    "data": [{"id": "/models/Qwen3.5-9B-Q4_K_M.gguf", "object": "model",
              "meta": {"n_vocab": 248320, "n_ctx": 40192, "n_ctx_train": 262144}}],
}


def _resolve(payload):
    resp = MagicMock()
    resp.json.return_value = payload
    with patch("httpx.get", return_value=resp):
        return resolve_context_window("http://llm:8092/v1")


def test_reads_the_live_n_ctx_from_llamacpp_meta_not_the_training_context():
    assert _resolve(LLAMACPP_MODELS) == 40192


def test_top_level_n_ctx_still_works():
    assert _resolve({"data": [{"id": "m", "n_ctx": 32000}]}) == 32000


def test_unknown_shape_still_falls_back():
    assert _resolve({"data": [{"id": "m"}]}) == 8000
