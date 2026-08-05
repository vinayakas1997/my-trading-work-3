"""Opt-in API key authentication for FastAPI services.

Usage:
    from vinu_infra.auth import require_auth
    @router.get("/protected", dependencies=[Depends(require_auth)])

All routes are open when VINU_API_KEY is not set.
When VINU_API_KEY is set, every endpoint with Depends(require_auth)
requires Authorization: Bearer <key>.
"""

from __future__ import annotations

import os

from fastapi import HTTPException, Request, status

VINU_API_KEY: str = os.getenv("VINU_API_KEY", "")


async def require_auth(request: Request) -> None:
    if not VINU_API_KEY:
        return
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or malformed Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = auth.removeprefix("Bearer ")
    if token != VINU_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key",
        )
