"""Global, cross-component model policy -- Decision 4 of
missing-pieces-of-system/new-theory-of-trading/01-planning.md.

Lives here (not inside vinu-initial-analysis) because vinu-infra is
already the one dependency shared across components (vinu-initial-
analysis, vinu-news, vinu-stock-price today) and already owns the
adjacent shared concern -- models.py's `ensure_model`, the shared model
registry/download logic every model-based angle already goes through.

Two knobs, both boot-only (`.env`-derived module-level constants, read
once at import), matching the existing precedent in
vinu-live/vinu_live/trade_plan/orchestrator.py: "feature kill switches
belong in .env, not a runtime HTTP surface" (RUNTIME_CORR_ENABLED there
is boot-only for the same reason; only numeric thresholds are made
live-editable via RuntimeSettings). Toggling whether a multi-hundred-MB
model gets loaded, or swapping which checkpoint loads, is exactly this
kind of restart-required change, not a live-tunable threshold:

1. `models_enabled()` -- VINU_MODELS_ENABLED, default true. When false,
   every angle tagged `category: model` in its own spec.yaml should be
   skipped by the caller (this module does not know about angles/specs
   itself, it only answers the yes/no policy question).
2. `get_model_checkpoint(angle_name, default)` -- per-angle string
   override, VINU_<ANGLE>_CHECKPOINT, mirroring the existing
   VINU_<ANGLE>_<SETTING> convention in
   vinu-initial-analysis/vinu_initial_analysis/config.py::get_angle_setting,
   extended to strings (that function is int-only today).

`policy_version()` is the version stamp Decision 7 requires every run/
row to carry -- a deterministic hash of the resolved policy (the
enabled flag plus every VINU_*_CHECKPOINT override actually set), so two
runs under the same env produce the same version and a changed env
produces a different one, without needing a live-editable counter.
"""

from __future__ import annotations

import hashlib
import os


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


# Boot-only: read once at import, like every other module-level policy
# constant in this codebase (e.g. orchestrator.py's RUNTIME_CORR_ENABLED).
MODELS_ENABLED: bool = _env_bool("VINU_MODELS_ENABLED", True)


def models_enabled() -> bool:
    """True unless VINU_MODELS_ENABLED is explicitly set to a falsy value.

    When false, callers (e.g. vinu-initial-analysis's AngleRunner) should
    skip every angle whose spec.yaml declares `category: model` --
    this function only answers the policy question, it does not know
    about angles/specs itself."""
    return MODELS_ENABLED


def get_model_checkpoint(angle_name: str, default: str) -> str:
    """Per-angle checkpoint/variant override: VINU_<ANGLE_NAME>_CHECKPOINT.

    Falls back to `default` (the angle's own already-decided checkpoint)
    when unset or blank. Mirrors vinu-initial-analysis's
    get_angle_setting() convention, extended to strings -- that function
    is int-only and can't express a checkpoint name like
    "amazon/chronos-t5-large".

    Called at each model-based angle's own compute.py module-import time
    (a module-level constant, evaluated once) -- same pattern as
    get_angle_setting()'s own MIN_OBSERVATIONS usage.
    """
    env_var = f"VINU_{angle_name.upper()}_CHECKPOINT"
    raw = os.getenv(env_var)
    if raw is not None and raw.strip():
        return raw.strip()
    return default


def _checkpoint_overrides_snapshot() -> dict[str, str]:
    """Every VINU_<ANGLE>_CHECKPOINT env var actually set right now, sorted
    by name -- the only part of the environment (besides MODELS_ENABLED)
    that policy_version() needs to be sensitive to."""
    overrides: dict[str, str] = {}
    for key, value in os.environ.items():
        if key.startswith("VINU_") and key.endswith("_CHECKPOINT") and value.strip():
            overrides[key] = value.strip()
    return dict(sorted(overrides.items()))


def policy_version() -> str:
    """Deterministic short hash of the resolved model policy (the enabled
    flag plus every checkpoint override actually set in the environment).

    Two runs under the same env produce the same version; a changed env
    (MODELS_ENABLED flipped, or a checkpoint override added/changed)
    produces a different one. This is the value Decision 7 says every
    run/row should stamp, so a historical row can always answer "what
    model policy was active when this was recorded" without needing a
    live-editable version counter -- the policy is boot-only, so a plain
    hash of its resolved state is enough."""
    overrides = _checkpoint_overrides_snapshot()
    material = f"models_enabled={MODELS_ENABLED};" + ";".join(
        f"{k}={v}" for k, v in overrides.items()
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:12]
