from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ProviderCapabilities:
    name: str
    capture_reasoning: bool = False
    send_reasoning_content: bool = False
    temperature_override: float | None = None
    normalize_assistant_content: bool = False
    default_headers: dict[str, str] = field(default_factory=dict)
    supports_streaming: bool = True
    max_tokens_default: int = 4096
    requires_api_key: bool = True
