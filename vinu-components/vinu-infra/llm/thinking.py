"""One switch for the hidden "thinking" of reasoning models served locally (llama.cpp, vLLM).

A thinking model spends most of its tokens (measured: ~70% on Qwen3.5-9B) on reasoning nobody reads, so a long prompt can
outrun the request timeout while the answer itself is short. Setting `VINU_LLM_ENABLE_THINKING=false` sends
`chat_template_kwargs: {"enable_thinking": false}` with every chat request, which those servers honour (the same
test call went from 22.8 s to 6.5 s). Unset or any other value sends nothing, so hosted providers see no change.
"""

from __future__ import annotations

import os


def thinking_extra() -> dict:
    """Extra request-body fields for OpenAI-compatible chat calls; empty unless thinking is explicitly turned off."""
    if os.environ.get("VINU_LLM_ENABLE_THINKING", "").strip().lower() in ("0", "false", "no", "off"):
        return {"chat_template_kwargs": {"enable_thinking": False}}
    return {}
