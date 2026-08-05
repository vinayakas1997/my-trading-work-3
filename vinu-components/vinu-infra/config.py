"""Shared service configuration from environment variables.

Usage:
    from vinu_infra.config import ServiceConfig, from_env

    config = from_env("VINU_NEWS", {"host": "127.0.0.1", "port": 8080})
    # Reads VINU_NEWS_HOST, VINU_NEWS_PORT, VINU_NEWS_LOG_LEVEL from env
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class MissingDataRootError(RuntimeError):
    """Raised when a service's required VINU_<PREFIX>_DATA_ROOT env var is unset."""


def require_data_root(prefix: str) -> Path:
    """Resolve a service's data root from its required env var.

    Every vinu-* service must set VINU_<prefix>_DATA_ROOT explicitly (in the
    environment or a loaded .env file) — there is no cwd-relative fallback.
    A silent default is what let the Docker root and the local-dev root
    drift apart in the first place; failing fast here is what prevents it.
    """
    var_name = f"VINU_{prefix}_DATA_ROOT"
    raw = os.environ.get(var_name, "").strip()
    if not raw:
        raise MissingDataRootError(
            f"{var_name} is not set. Set it explicitly (e.g. in a .env file) "
            f"before starting this service — there is no default data root."
        )
    return Path(raw)


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
