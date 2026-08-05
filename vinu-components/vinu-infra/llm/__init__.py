"""Shared LLM client module for all vinu services.

Usage:
    from vinu_infra.llm import LlmClient, AsyncLlmClient, LlmConfig

    # Sync (for vinu-news, vinu-agent)
    client = LlmClient()
    result = client.chat_json(system, user)

    # Async (for vinu-research)
    client = AsyncLlmClient()
    result = await client.chat_json(system, user)
"""

from vinu_infra.llm.config import LlmConfig
from vinu_infra.llm.client import LlmClient
from vinu_infra.llm.client_async import AsyncLlmClient

__all__ = ["LlmConfig", "LlmClient", "AsyncLlmClient"]
