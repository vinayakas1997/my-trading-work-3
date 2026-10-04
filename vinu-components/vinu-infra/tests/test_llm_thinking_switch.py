"""VINU_LLM_ENABLE_THINKING=false turns off the hidden reasoning of local reasoning models on every chat request."""

from __future__ import annotations

import pytest

from vinu_infra.llm.thinking import thinking_extra


def test_nothing_is_sent_by_default(monkeypatch):
    monkeypatch.delenv("VINU_LLM_ENABLE_THINKING", raising=False)
    assert thinking_extra() == {}


@pytest.mark.parametrize("value", ["false", "False", "0", "no", "off", " FALSE "])
def test_false_turns_thinking_off(monkeypatch, value):
    monkeypatch.setenv("VINU_LLM_ENABLE_THINKING", value)
    assert thinking_extra() == {"chat_template_kwargs": {"enable_thinking": False}}


@pytest.mark.parametrize("value", ["true", "1", "", "maybe"])
def test_anything_else_sends_nothing(monkeypatch, value):
    monkeypatch.setenv("VINU_LLM_ENABLE_THINKING", value)
    assert thinking_extra() == {}


def test_the_shared_client_puts_it_in_the_request_body(monkeypatch):
    """The payload the infra client sends carries the switch (checked on the source, the request itself needs a server)."""
    from pathlib import Path
    root = Path(__file__).resolve().parents[1] / "llm"
    for name in ("client.py", "client_async.py"):
        assert "payload.update(thinking_extra())" in (root / name).read_text(encoding="utf-8"), name
