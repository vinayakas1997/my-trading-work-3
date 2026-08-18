"""Opt-in API key authentication for FastAPI services.

Usage:
    from vinu_infra.auth import require_auth
    @router.get("/protected", dependencies=[Depends(require_auth)])

All routes are open when VINU_API_KEY is not set.
When VINU_API_KEY is set, every endpoint with Depends(require_auth)
requires Authorization: Bearer <key>.
"""

from __future__ import annotations

import hmac
import os

from fastapi import HTTPException, Request, status

from vinu_infra.secrets_loader import load_secret

# The internal service-to-service auth key (implementation-plan task 11).
# Resolved through the Docker-secrets loader so the deployed value comes from
# /run/secrets/vinu_api_key (never a plain-text .env); local dev falls back
# to the VINU_API_KEY env var. Read at import time -- rotation restarts the
# container -- but keep the loader call so the mounted-file path is honored.
VINU_API_KEY: str = load_secret("vinu_api_key", "VINU_API_KEY") or os.getenv("VINU_API_KEY", "") or ""


async def require_auth(request: Request) -> None:
    if not VINU_API_KEY:
        return
    # Health/liveness endpoints must stay reachable without credentials --
    # Docker Compose's own healthcheck (and any orchestrator's probe) calls
    # these with no Authorization header. Without this, enabling
    # VINU_API_KEY makes every service whose /health route lives inside the
    # auth-wrapped router (expose_health_on_root=False) fail its own
    # healthcheck forever, which cascades into every depends_on: sub failing
    # to start (confirmed 2026-08-18 against the real Docker Compose stack).
    if request.url.path.endswith("/health"):
        return
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or malformed Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = auth.removeprefix("Bearer ")
    # hmac.compare_digest, not `!=` -- a plain string comparison short-
    # circuits on the first mismatched byte, so its response time leaks how
    # many leading characters of a guessed token are correct (a real,
    # well-known timing-attack class against API key checks).
    if not hmac.compare_digest(token, VINU_API_KEY):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key",
        )
