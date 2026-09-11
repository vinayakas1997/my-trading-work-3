"""Process-local, live-editable settings for a whitelisted set of tuning
knobs, exposed over HTTP so an operator can adjust them while the service
keeps running -- no container restart, no `.env` edit.

This is deliberately NOT a way to change everything at runtime. Secrets,
hard safety ceilings, and anything a service only reads once at import time
still live in `.env` / mandate.yaml and require a restart to change -- that
boundary is the point, not a limitation to work around. Only knobs a
service explicitly `register()`s here become live-editable, and every
value handed to `set()` is validated (cast, min/max) before it takes
effect, so the HTTP surface can't be used to push a knob outside the range
its own service considers safe.

Overrides live only in this process's memory. A restart reverts every knob
to its `.env`-derived default. That's deliberate: an env var always
describes what the container will actually do on its next boot, and a live
override should never silently outlive the process that made it or hide in
a file nobody re-reads a year later. If a change needs to survive a
restart, put it in `.env` / mandate.yaml instead.

Usage (inside a service):
    from vinu_infra.runtime_settings import RuntimeSettings

    SETTINGS = RuntimeSettings()
    SETTINGS.register(
        "runtime_corr_threshold",
        default=float(os.environ.get("VINU_LIVE_RUNTIME_CORR_THRESHOLD", "0.85")),
        minimum=0.0,
        maximum=1.0,
        description="Co-movement threshold above which the runtime correlation monitor trims.",
    )
    ...
    threshold = SETTINGS.get("runtime_corr_threshold")  # instead of a frozen module constant

Usage (exposing it over HTTP, reusing the service's existing auth):
    from vinu_infra.runtime_settings import build_admin_settings_router
    app.include_router(build_admin_settings_router(SETTINGS), dependencies=[Depends(require_auth)])
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any, Callable

from fastapi import APIRouter, Header, HTTPException


@dataclass(frozen=True)
class _Knob:
    default: Any
    caster: Callable[[Any], Any]
    minimum: float | None
    maximum: float | None
    description: str


class RuntimeSettings:
    """A small thread-safe registry: name -> (validated) current value.

    One instance per service (module-level singleton), not shared across
    services or processes -- each service's admin router only ever exposes
    its own instance.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._knobs: dict[str, _Knob] = {}
        self._overrides: dict[str, Any] = {}
        # Stage A (A32): monotonic counter, bumped on every effective set()/
        # reset(). An admin client can read it (snapshot / the router's GET),
        # then pass it back as `expected_version` on a PATCH to get a 409
        # instead of silently clobbering a change another operator made in
        # between. In-memory only, like the overrides themselves -- there's
        # no file to write atomically here (that half of daily_stock_analysis's
        # pattern doesn't apply to a process-local registry).
        self._version = 0

    def register(
        self,
        name: str,
        default: Any,
        *,
        caster: Callable[[Any], Any] = float,
        minimum: float | None = None,
        maximum: float | None = None,
        description: str = "",
    ) -> None:
        """Whitelist one knob. Call this at module import time (alongside
        the `.env` read that produces `default`), before any `.get()`."""
        with self._lock:
            self._knobs[name] = _Knob(default, caster, minimum, maximum, description)

    def get(self, name: str) -> Any:
        with self._lock:
            if name not in self._knobs:
                raise KeyError(f"Unknown setting: {name!r}")
            return self._overrides.get(name, self._knobs[name].default)

    def set(self, name: str, value: Any) -> Any:
        with self._lock:
            if name not in self._knobs:
                raise KeyError(f"Unknown setting: {name!r}")
            knob = self._knobs[name]
            try:
                cast = knob.caster(value)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{name}: cannot convert {value!r}: {exc}") from exc
            if knob.minimum is not None and cast < knob.minimum:
                raise ValueError(f"{name} must be >= {knob.minimum} (got {cast})")
            if knob.maximum is not None and cast > knob.maximum:
                raise ValueError(f"{name} must be <= {knob.maximum} (got {cast})")
            changed = self._overrides.get(name, knob.default) != cast
            self._overrides[name] = cast
            if changed:
                self._version += 1
            return cast

    def reset(self, name: str) -> Any:
        """Drop the override -- back to the `.env`-derived default."""
        with self._lock:
            if name not in self._knobs:
                raise KeyError(f"Unknown setting: {name!r}")
            if self._overrides.pop(name, None) is not None:
                self._version += 1
            return self._knobs[name].default

    @property
    def version(self) -> int:
        with self._lock:
            return self._version

    def check_version(self, expected: int) -> None:
        """Raise ValueError if `expected` doesn't match the current version --
        the optimistic-concurrency guard for a multi-operator admin API."""
        with self._lock:
            if expected != self._version:
                raise ValueError(
                    f"version mismatch: expected {expected}, current {self._version} "
                    f"-- settings changed since you last read them"
                )

    def overrides(self) -> dict[str, Any]:
        """Only the knobs an admin call has actually changed -- for a
        caller that wants to overlay live overrides on top of some other
        source (a config file, an env var) without touching knobs nobody
        has ever set() on this process."""
        with self._lock:
            return dict(self._overrides)

    def snapshot(self) -> dict[str, dict[str, Any]]:
        with self._lock:
            return {
                name: {
                    "value": self._overrides.get(name, knob.default),
                    "default": knob.default,
                    "overridden": name in self._overrides,
                    "min": knob.minimum,
                    "max": knob.maximum,
                    "description": knob.description,
                }
                for name, knob in self._knobs.items()
            }


def build_admin_settings_router(
    settings: RuntimeSettings,
    *,
    prefix: str = "/admin/settings",
    on_change: Callable[[str, dict[str, Any]], None] | None = None,
) -> APIRouter:
    """GET/PATCH/reset over one RuntimeSettings instance. Mount it under
    the same router (or with the same `Depends(require_auth)`) the rest of
    the service uses -- this deliberately does not add its own auth, so it
    never becomes a second credential to manage or a bypass of the first.

    `on_change(action, changes)` -- if given -- is called after a
    successful mutation: `action` is `"set"` or `"reset"`, `changes` maps
    knob name to its new value. It's how a service records a runtime risk-
    limit change into its own audit trail (NautilusTrader's
    `set_max_notional_per_order()` emits an event the same way). Kept as an
    injected callback rather than an import so this module stays free of
    any service's logging/audit dependencies. Any exception it raises is
    swallowed -- an audit-write hiccup must not fail the setting change
    that already took effect, the same ordering every audit write in this
    codebase follows."""
    router = APIRouter(prefix=prefix, tags=["admin"])

    def _emit(action: str, changes: dict[str, Any]) -> None:
        if on_change is None or not changes:
            return
        try:
            on_change(action, changes)
        except Exception:  # noqa: BLE001 -- audit write never blocks the real change
            import logging

            logging.getLogger(__name__).exception(
                "runtime-settings on_change callback failed for %s %s", action, changes,
            )

    @router.get("")
    async def list_settings() -> dict[str, Any]:
        # A32: `version` is the token a client echoes back as `If-Match` on a
        # PATCH to get optimistic-concurrency protection. `settings` keeps the
        # per-knob shape callers already expect.
        return {"version": settings.version, "settings": settings.snapshot()}

    def _require_match(if_match: str | None) -> None:
        if if_match is None or if_match == "*":
            return
        try:
            expected = int(if_match.strip().strip('"'))
        except ValueError:
            raise HTTPException(status_code=400, detail=f"If-Match must be an integer version, got {if_match!r}")
        try:
            settings.check_version(expected)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @router.patch("")
    async def update_settings(
        body: dict[str, Any], if_match: str | None = Header(default=None),
    ) -> dict[str, Any]:
        if not body:
            raise HTTPException(status_code=422, detail="No settings given")
        _require_match(if_match)
        updated: dict[str, Any] = {}
        errors: dict[str, str] = {}
        for name, value in body.items():
            try:
                updated[name] = settings.set(name, value)
            except KeyError as exc:
                errors[name] = str(exc)
            except ValueError as exc:
                errors[name] = str(exc)
        if errors and not updated:
            raise HTTPException(status_code=422, detail=errors)
        _emit("set", updated)
        result: dict[str, Any] = {"updated": updated, "version": settings.version}
        if errors:
            result["errors"] = errors
        return result

    @router.post("/{name}/reset")
    async def reset_setting(name: str, if_match: str | None = Header(default=None)) -> dict[str, Any]:
        _require_match(if_match)
        try:
            value = settings.reset(name)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        _emit("reset", {name: value})
        return {"name": name, "value": value, "version": settings.version}

    return router
