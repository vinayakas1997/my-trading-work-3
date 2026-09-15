"""Per-role LLM configuration.

Lets a call site say "I am the `orchestrator`" (or `forecast_skill`, or
anything else) instead of every LlmConfig-constructing call site
hardcoding its own base_url/model. A role missing from `roles.json` (or
the file itself missing/empty) falls all the way back to
`LlmConfig.from_env()` -- today's exact behavior -- so adding a new role
to a call site never requires editing this file first, and the file
ships with every role empty so nothing's behavior changes until an
operator deliberately fills one in.

Precedence, highest to lowest:
1. `VINU_LLM_ROLE_<ROLE>_<FIELD>` env var (per-role, per-field override)
2. `roles.json`'s `roles.<role>` block
3. `roles.json`'s `default` block
4. Plain `VINU_LLM_*` env defaults (`LlmConfig.from_env()`)

See missing-pieces-of-system/llm-configuration-settings-system/ for the
full design.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from vinu_infra.llm.config import LlmConfig

_DEFAULT_ROLES_PATH = Path(__file__).resolve().parent / "roles.json"
_ROLE_ENV_PREFIX = "VINU_LLM_ROLE"

# Fields a role block (or a per-field env override) may set. Anything
# else -- ttl_sec, circuit_threshold, rate_limit, etc. -- always comes
# from the plain VINU_LLM_* env defaults; roles only cover the fields
# that actually vary by call site in practice.
_ROLE_FIELDS = ("base_url", "model", "api_key", "max_tokens", "timeout_sec", "retry_max")

_loaded_path: str | None = None
_loaded_data: dict[str, Any] | None = None


def _roles_path() -> Path:
    override = os.environ.get("VINU_LLM_ROLES_PATH")
    return Path(override) if override else _DEFAULT_ROLES_PATH


def _load_roles_file() -> dict[str, Any]:
    global _loaded_path, _loaded_data
    path = _roles_path()
    key = str(path)
    if _loaded_data is not None and _loaded_path == key:
        return _loaded_data
    if not path.exists():
        _loaded_data, _loaded_path = {"default": {}, "roles": {}}, key
        return _loaded_data
    try:
        _loaded_data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        _loaded_data = {"default": {}, "roles": {}}
    _loaded_path = key
    return _loaded_data


def _role_block(role: str) -> dict[str, Any]:
    data = _load_roles_file()
    return data.get("roles", {}).get(role) or {}


def _role_env(role: str, field: str) -> str | None:
    key = f"{_ROLE_ENV_PREFIX}_{role.upper()}_{field.upper()}"
    val = os.environ.get(key)
    return val if val else None


def has_role_override(role: str) -> bool:
    """True if `role` has any real configuration -- either a non-empty
    block in roles.json or at least one per-field env override. Lets a
    caller distinguish "this role is deliberately configured" from "this
    role doesn't exist, fall back to something else" without having to
    inspect the resolved LlmConfig's field values (which can't be told
    apart from plain env defaults just by looking at them)."""
    if _role_block(role):
        return True
    return any(_role_env(role, field) is not None for field in _ROLE_FIELDS)


def get_llm_config_for_role(role: str) -> LlmConfig:
    """Resolve `role`'s config per the precedence order in the module
    docstring. A role with no configuration anywhere returns exactly
    what `LlmConfig.from_env()` would -- this function is always safe to
    call, even for a role nobody has configured yet."""
    merged = dict(_load_roles_file().get("default") or {})
    merged.update(_role_block(role))

    overrides: dict[str, Any] = {}
    for field in _ROLE_FIELDS:
        env_val = _role_env(role, field)
        if env_val is not None:
            overrides[field] = env_val
        elif field in merged:
            overrides[field] = merged[field]

    api_key_env = merged.get("api_key_env")
    if api_key_env and "api_key" not in overrides:
        env_key = os.environ.get(api_key_env)
        if env_key:
            overrides["api_key"] = env_key

    return LlmConfig.from_env(**overrides)
