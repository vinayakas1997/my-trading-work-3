"""Shared service configuration from environment variables.

Usage:
    from vinu_lib.config import ServiceConfig, from_env

    config = from_env("VINU_NEWS", {"host": "127.0.0.1", "port": 8080})
    # Reads VINU_NEWS_HOST, VINU_NEWS_PORT, VINU_NEWS_LOG_LEVEL from env
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ServiceConfig:
    host: str = "127.0.0.1"
    port: int = 8080
    log_level: str = "INFO"
    env: str = "development"
    extra: dict[str, Any] = field(default_factory=dict)


def from_env(
    prefix: str,
    defaults: dict[str, Any] | None = None,
) -> ServiceConfig:
    d = defaults or {}
    return ServiceConfig(
        host=os.environ.get(f"{prefix}_HOST", str(d.get("host", "127.0.0.1"))),
        port=int(os.environ.get(f"{prefix}_PORT", str(d.get("port", 8080)))),
        log_level=os.environ.get(f"{prefix}_LOG_LEVEL", str(d.get("log_level", "INFO"))).upper(),
        env=os.environ.get(f"{prefix}_ENV", str(d.get("env", "development"))).lower(),
    )
