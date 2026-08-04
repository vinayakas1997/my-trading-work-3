import json
import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, Generator, Optional

from ..config import AgentConfig

LOG = logging.getLogger(__name__)

_DEFAULT_CONTEXT_WINDOW = 8000
_CONTEXT_WINDOW_FIELDS = ("n_ctx", "context_length", "context_window", "max_context_length")


def resolve_context_window(base_url: str, model: str = "", timeout: float = 5.0) -> int:
    """Query an OpenAI-compatible `/models` endpoint for the real context
    window, instead of trusting a hardcoded constant.

    Directly answers 04-advanced-aim-1's headline finding
    (end-to-end-complete-status.md §2.1/§3): `loop.py`'s context-management
    budget was hardcoded to 128000 while the real deployed model
    (`qwen36-35B`, served via llama.cpp) had a real context window of
    32000 — confirmed via `curl http://localhost:8009/v1/models` returning
    `"n_ctx": 32000`. llama.cpp's `/v1/models` response includes `n_ctx`
    directly; this checks a handful of common field names so it also works
    against other OpenAI-compatible servers that expose the value under a
    different key.

    Falls back to a conservative default — logged, not silent — rather
    than trusting an unverified number: same discipline this project
    already uses elsewhere (`FreshnessChecker` labels stale data instead of
    presenting it with full confidence).
    """
    if not base_url:
        return _DEFAULT_CONTEXT_WINDOW
    try:
        import httpx

        url = base_url.rstrip("/") + "/models"
        resp = httpx.get(url, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        candidates: list[dict] = []
        if isinstance(data, dict):
            candidates.append(data)
            for item in data.get("data", []) or []:
                if isinstance(item, dict):
                    candidates.append(item)
        for c in candidates:
            for field_name in _CONTEXT_WINDOW_FIELDS:
                val = c.get(field_name)
                if isinstance(val, int) and val > 0:
                    return val
    except Exception as e:
        LOG.warning(
            "Could not resolve context window from %s: %s — falling back to %d",
            base_url, e, _DEFAULT_CONTEXT_WINDOW,
        )
    return _DEFAULT_CONTEXT_WINDOW


class ChatLLM(ABC):
    #: Real context window this LLM's backing model actually supports.
    #: Set by `create_llm()` after construction — either from
    #: `AgentConfig.llm.context_window` (explicit override) or auto-resolved
    #: via `resolve_context_window()`. Never silently defaults to a number
    #: that hasn't been verified against the real model.
    context_window: int = _DEFAULT_CONTEXT_WINDOW

    @abstractmethod
    def chat(self, messages: list, tools: Optional[list] = None, **kwargs) -> dict:
        """Returns at minimum {"content": str}, optionally "tool_calls".

        Also populates, when the provider actually returns them (never
        fabricated):
        - "usage": {"prompt_tokens", "completion_tokens", "total_tokens"} —
          real counts from the provider's own tokenizer, not the char/4
          heuristic `agent/loop.py::_estimate_tokens` falls back to when
          this key is absent.
        - "retry_count": int — number of retries actually taken before this
          call succeeded (0 = succeeded on the first attempt). Every
          subclass below now retries explicitly with `max_retries=0` on the
          underlying SDK client, specifically so this count is real instead
          of hidden inside the SDK's own opaque internal retry logic (the
          gap 04-advanced-aim-1 found in `OpenAIChatLLM` specifically —
          `max_retries=3` handed straight to the SDK, invisible to every
          caller).
        """
        ...

    def chat_stream(self, messages: list, tools: Optional[list] = None, **kwargs) -> Generator[dict, None, None]:
        raise NotImplementedError

    @property
    def model(self) -> str:
        return ""

    @property
    def base_url(self) -> str:
        return ""


def _is_transient_openai_error(e: Exception) -> bool:
    try:
        from openai import APIConnectionError, APITimeoutError, InternalServerError, RateLimitError
        if isinstance(e, (APIConnectionError, APITimeoutError, RateLimitError, InternalServerError)):
            return True
    except ImportError:
        pass
    status = getattr(e, "status_code", None)
    return status is not None and (status == 429 or status >= 500)


class OpenAIChatLLM(ChatLLM):
    def __init__(
        self, model: str = "gpt-4o-mini", api_key: str = "", base_url: str = "",
        timeout: int = 120, retry_max: int = 3,
    ):
        from openai import OpenAI
        self._client = OpenAI(
            api_key=api_key or "sk-placeholder",
            base_url=base_url or None,
            # max_retries=0: retry explicitly below instead of via the SDK's
            # own internal retry, which counts attempts nobody outside the
            # SDK can see — see ChatLLM.chat's docstring.
            max_retries=0,
            timeout=timeout,
        )
        self._model = model
        self._base_url = base_url
        self._timeout = timeout
        self._retry_max = max(1, retry_max)

    @property
    def model(self) -> str:
        return self._model

    @property
    def base_url(self) -> str:
        return self._base_url

    def chat(self, messages: list, tools: Optional[list] = None, **kwargs) -> dict:
        params = {"model": self._model, "messages": messages}
        if tools:
            params["tools"] = tools
            params["tool_choice"] = "auto"

        last_error: Exception | None = None
        for attempt in range(self._retry_max):
            try:
                response = self._client.chat.completions.create(**params)
            except Exception as e:
                last_error = e
                if attempt < self._retry_max - 1 and _is_transient_openai_error(e):
                    delay = (2 ** attempt) * 1.0
                    LOG.warning(
                        "OpenAI LLM call failed (%s), retrying in %.1fs (attempt %d/%d)",
                        type(e).__name__, delay, attempt + 1, self._retry_max,
                    )
                    time.sleep(delay)
                    continue
                raise RuntimeError(
                    f"OpenAI LLM call failed after {attempt + 1} attempt(s): {e}"
                ) from e

            result: dict[str, Any] = {
                "content": response.choices[0].message.content or "",
                "retry_count": attempt,
            }
            tool_calls = response.choices[0].message.tool_calls
            if tool_calls:
                result["tool_calls"] = [
                    {
                        "id": tc.id,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in tool_calls
                ]
            usage = getattr(response, "usage", None)
            if usage is not None:
                result["usage"] = {
                    "prompt_tokens": getattr(usage, "prompt_tokens", 0) or 0,
                    "completion_tokens": getattr(usage, "completion_tokens", 0) or 0,
                    "total_tokens": getattr(usage, "total_tokens", 0) or 0,
                }
            return result

        raise RuntimeError(f"OpenAI LLM call failed after {self._retry_max} attempt(s): {last_error}") from last_error


class DeepSeekChatLLM(OpenAIChatLLM):
    def __init__(self, model: str = "deepseek-chat", api_key: str = "", base_url: str = "", timeout: int = 120):
        base_url = base_url or "https://api.deepseek.com/v1"
        super().__init__(model=model, api_key=api_key, base_url=base_url, timeout=timeout)


def _is_transient_anthropic_error(e: Exception) -> bool:
    try:
        from anthropic import APIConnectionError, APITimeoutError, InternalServerError, RateLimitError
        if isinstance(e, (APIConnectionError, APITimeoutError, RateLimitError, InternalServerError)):
            return True
    except ImportError:
        pass
    status = getattr(e, "status_code", None)
    return status is not None and (status == 429 or status >= 500)


class AnthropicChatLLM(ChatLLM):
    def __init__(self, model: str = "claude-sonnet-4-20250514", api_key: str = "", timeout: int = 120, retry_max: int = 3):
        self._api_key = api_key
        self._model = model
        self._timeout = timeout
        self._retry_max = max(1, retry_max)

    @property
    def model(self) -> str:
        return self._model

    def chat(self, messages: list, tools: Optional[list] = None, **kwargs) -> dict:
        from anthropic import Anthropic
        # max_retries=0: same reasoning as OpenAIChatLLM — retry explicitly
        # below so retry_count is real, not hidden inside the SDK.
        client = Anthropic(api_key=self._api_key, max_retries=0)

        system = None
        msgs = []
        for m in messages:
            if m.get("role") == "system":
                system = m["content"]
            else:
                msgs.append({"role": m["role"], "content": m["content"]})

        params: dict = {"model": self._model, "max_tokens": 4096, "messages": msgs}
        if system:
            params["system"] = system
        if tools:
            params["tools"] = [
                {
                    "name": t["function"]["name"],
                    "description": t["function"]["description"],
                    "input_schema": t["function"]["parameters"],
                }
                for t in tools
            ]

        last_error: Exception | None = None
        for attempt in range(self._retry_max):
            try:
                response = client.messages.create(**params)
            except Exception as e:
                last_error = e
                if attempt < self._retry_max - 1 and _is_transient_anthropic_error(e):
                    delay = (2 ** attempt) * 1.0
                    LOG.warning(
                        "Anthropic LLM call failed (%s), retrying in %.1fs (attempt %d/%d)",
                        type(e).__name__, delay, attempt + 1, self._retry_max,
                    )
                    time.sleep(delay)
                    continue
                raise RuntimeError(
                    f"Anthropic LLM call failed after {attempt + 1} attempt(s): {e}"
                ) from e

            result: dict[str, Any] = {"content": "", "retry_count": attempt}
            tool_calls = []
            for block in response.content:
                if block.type == "text":
                    result["content"] = block.text
                elif block.type == "tool_use":
                    tool_calls.append({
                        "id": block.id,
                        "function": {
                            "name": block.name,
                            "arguments": json.dumps(block.input),
                        },
                    })
            if tool_calls:
                result["tool_calls"] = tool_calls
            usage = getattr(response, "usage", None)
            if usage is not None:
                input_tokens = getattr(usage, "input_tokens", 0) or 0
                output_tokens = getattr(usage, "output_tokens", 0) or 0
                result["usage"] = {
                    "prompt_tokens": input_tokens,
                    "completion_tokens": output_tokens,
                    "total_tokens": input_tokens + output_tokens,
                }
            return result

        raise RuntimeError(f"Anthropic LLM call failed after {self._retry_max} attempt(s): {last_error}") from last_error


class OllamaChatLLM(ChatLLM):
    def __init__(self, model: str = "llama3", base_url: str = "", timeout: int = 120, retry_max: int = 3):
        self._base_url = base_url or "http://localhost:11434"
        self._model = model
        self._timeout = timeout
        self._retry_max = max(1, retry_max)

    @property
    def model(self) -> str:
        return self._model

    @property
    def base_url(self) -> str:
        return self._base_url

    def chat(self, messages: list, tools: Optional[list] = None, **kwargs) -> dict:
        import requests

        payload: dict = {"model": self._model, "messages": messages, "stream": False}
        if tools:
            payload["tools"] = tools

        last_error: Exception | None = None
        for attempt in range(self._retry_max):
            try:
                resp = requests.post(
                    f"{self._base_url}/api/chat",
                    json=payload,
                    timeout=self._timeout,
                )
                resp.raise_for_status()
                data = resp.json()
                result: dict[str, Any] = {
                    "content": data.get("message", {}).get("content", ""),
                    "retry_count": attempt,
                }
                tool_calls = data.get("message", {}).get("tool_calls")
                if tool_calls:
                    result["tool_calls"] = [
                        {
                            "id": tc.get("id", f"call_{i}"),
                            "function": {
                                "name": tc["function"]["name"],
                                "arguments": json.dumps(tc["function"]["arguments"]),
                            },
                        }
                        for i, tc in enumerate(tool_calls)
                    ]
                # Ollama returns these when the backing model reports them —
                # real tokenizer counts, not an estimate.
                if "prompt_eval_count" in data or "eval_count" in data:
                    prompt_tokens = data.get("prompt_eval_count", 0) or 0
                    completion_tokens = data.get("eval_count", 0) or 0
                    result["usage"] = {
                        "prompt_tokens": prompt_tokens,
                        "completion_tokens": completion_tokens,
                        "total_tokens": prompt_tokens + completion_tokens,
                    }
                return result
            except (requests.ConnectionError, requests.Timeout) as e:
                last_error = e
                if attempt < self._retry_max - 1:
                    time.sleep((2 ** attempt) * 1.0)
                    continue
            except requests.RequestException as e:
                last_error = e
                status = e.response.status_code if hasattr(e, 'response') and e.response is not None else None
                if status is not None and (status == 429 or status >= 500) and attempt < self._retry_max - 1:
                    time.sleep((2 ** attempt) * 1.0)
                    continue
                raise RuntimeError(f"Ollama LLM call failed: {e}") from e

        raise RuntimeError(f"Ollama LLM call failed after {self._retry_max} attempts: {last_error}")


def create_llm(config: AgentConfig) -> ChatLLM:
    provider = config.llm.provider.lower()
    if provider == "openai":
        llm: ChatLLM = OpenAIChatLLM(
            model=config.llm.model_name,
            api_key=config.llm.api_key,
            base_url=config.llm.base_url,
            timeout=config.llm.timeout,
        )
    elif provider == "deepseek":
        llm = DeepSeekChatLLM(
            model=config.llm.model_name,
            api_key=config.llm.api_key,
            base_url=config.llm.base_url,
            timeout=config.llm.timeout,
        )
    elif provider == "anthropic":
        llm = AnthropicChatLLM(
            model=config.llm.model_name,
            api_key=config.llm.api_key,
            timeout=config.llm.timeout,
        )
    elif provider == "ollama":
        llm = OllamaChatLLM(
            model=config.llm.model_name,
            base_url=config.llm.base_url,
            timeout=config.llm.timeout,
        )
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")

    llm.context_window = (
        config.llm.context_window
        if config.llm.context_window > 0
        else resolve_context_window(llm.base_url, llm.model)
    )
    return llm
