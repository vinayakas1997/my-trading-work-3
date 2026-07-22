import json
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, Generator, List, Optional

from ..config import AgentConfig


class ChatLLM(ABC):
    @abstractmethod
    def chat(self, messages: list, tools: Optional[list] = None, **kwargs) -> dict:
        ...

    def chat_stream(self, messages: list, tools: Optional[list] = None, **kwargs) -> Generator[dict, None, None]:
        raise NotImplementedError


class OpenAIChatLLM(ChatLLM):
    def __init__(self, model: str = "gpt-4o-mini", api_key: str = "", base_url: str = "", timeout: int = 120):
        from openai import OpenAI
        self._client = OpenAI(
            api_key=api_key or "sk-placeholder",
            base_url=base_url or None,
            max_retries=3,
            timeout=timeout,
        )
        self._model = model
        self._timeout = timeout

    def chat(self, messages: list, tools: Optional[list] = None, **kwargs) -> dict:
        params = {"model": self._model, "messages": messages}
        if tools:
            params["tools"] = tools
            params["tool_choice"] = "auto"

        try:
            response = self._client.chat.completions.create(**params)
        except Exception as e:
            raise RuntimeError(f"OpenAI LLM call failed after retries: {e}") from e

        result = {"content": response.choices[0].message.content or ""}
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
        return result


class DeepSeekChatLLM(OpenAIChatLLM):
    def __init__(self, model: str = "deepseek-chat", api_key: str = "", base_url: str = "", timeout: int = 120):
        base_url = base_url or "https://api.deepseek.com/v1"
        super().__init__(model=model, api_key=api_key, base_url=base_url, timeout=timeout)


class AnthropicChatLLM(ChatLLM):
    def __init__(self, model: str = "claude-sonnet-4-20250514", api_key: str = "", timeout: int = 120):
        self._api_key = api_key
        self._model = model
        self._timeout = timeout

    def chat(self, messages: list, tools: Optional[list] = None, **kwargs) -> dict:
        from anthropic import Anthropic
        client = Anthropic(api_key=self._api_key, max_retries=3)

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

        try:
            response = client.messages.create(**params)
        except Exception as e:
            raise RuntimeError(f"Anthropic LLM call failed after retries: {e}") from e

        result = {"content": ""}
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
        return result


class OllamaChatLLM(ChatLLM):
    def __init__(self, model: str = "llama3", base_url: str = "", timeout: int = 120):
        self._base_url = base_url or "http://localhost:11434"
        self._model = model
        self._timeout = timeout

    def chat(self, messages: list, tools: Optional[list] = None, **kwargs) -> dict:
        import requests

        payload: dict = {"model": self._model, "messages": messages, "stream": False}
        if tools:
            payload["tools"] = tools

        retry_max = 3
        last_error: Exception | None = None
        for attempt in range(retry_max):
            try:
                resp = requests.post(
                    f"{self._base_url}/api/chat",
                    json=payload,
                    timeout=self._timeout,
                )
                resp.raise_for_status()
                data = resp.json()
                result = {"content": data.get("message", {}).get("content", "")}
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
                return result
            except (requests.ConnectionError, requests.Timeout) as e:
                last_error = e
                if attempt < retry_max - 1:
                    time.sleep((2 ** attempt) * 1.0)
                    continue
            except requests.RequestException as e:
                last_error = e
                status = e.response.status_code if hasattr(e, 'response') and e.response is not None else None
                if status is not None and (status == 429 or status >= 500) and attempt < retry_max - 1:
                    time.sleep((2 ** attempt) * 1.0)
                    continue
                raise RuntimeError(f"Ollama LLM call failed: {e}") from e

        raise RuntimeError(f"Ollama LLM call failed after {retry_max} attempts: {last_error}")


def create_llm(config: AgentConfig) -> ChatLLM:
    provider = config.llm.provider.lower()
    if provider == "openai":
        return OpenAIChatLLM(
            model=config.llm.model_name,
            api_key=config.llm.api_key,
            base_url=config.llm.base_url,
            timeout=config.llm.timeout,
        )
    elif provider == "deepseek":
        return DeepSeekChatLLM(
            model=config.llm.model_name,
            api_key=config.llm.api_key,
            base_url=config.llm.base_url,
            timeout=config.llm.timeout,
        )
    elif provider == "anthropic":
        return AnthropicChatLLM(
            model=config.llm.model_name,
            api_key=config.llm.api_key,
            timeout=config.llm.timeout,
        )
    elif provider == "ollama":
        return OllamaChatLLM(
            model=config.llm.model_name,
            base_url=config.llm.base_url,
            timeout=config.llm.timeout,
        )
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")
