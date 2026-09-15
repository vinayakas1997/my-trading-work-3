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
from vinu_infra.llm.retry import LlmCallFailed, LlmParseError, build_async_retry, build_retry
from vinu_infra.llm.roles import get_llm_config_for_role, has_role_override

__all__ = [
    "LlmConfig",
    "LlmClient",
    "AsyncLlmClient",
    "LlmCallFailed",
    "LlmParseError",
    "build_retry",
    "build_async_retry",
    "get_llm_config_for_role",
    "has_role_override",
]
