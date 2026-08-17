"""Docker-secrets-backed credential loader (implementation-plan task 13).

Resolution order for any credential:
  1. A Docker secret file mounted at ``<VINU_SECRETS_DIR>/<secret_name>``
     (default ``/run/secrets/<secret_name>``) -- the deployed-container path.
  2. The legacy env var (when supplied) -- local-dev fallback / non-secret
     overrides.

Deployed containers mount real credentials under ``/run/secrets`` via
``docker-compose`` ``secrets:`` (see the repo-root ``docker-compose.yml`` and
``scripts/setup-secrets.sh``); plain ``.env`` is reserved for non-secret config
and local development. Reading a secret never logs or otherwise surfaces its
value; it returns only the string.
"""

from __future__ import annotations

import os
from pathlib import Path


def secrets_dir() -> Path:
    """Directory holding secret files. Overridable via ``VINU_SECRETS_DIR``
    so tests can point it at a temp dir instead of the container default."""
    return Path(os.environ.get("VINU_SECRETS_DIR", "/run/secrets"))


def load_secret(secret_name: str, env_var: str | None = None) -> str | None:
    """Return the credential value, or ``None`` if it cannot be found.

    Prefers a mounted Docker secret file ``<VINU_SECRETS_DIR>/<secret_name>``;
    falls back to the legacy ``env_var``. Reads at call time so tests can set
    ``VINU_SECRETS_DIR`` and so a rotated secret file is picked up on the next
    read.
    """
    path = secrets_dir() / secret_name
    try:
        if path.is_file():
            value = path.read_text().strip()
            if value:
                return value
    except OSError:
        pass
    if env_var:
        return os.environ.get(env_var)
    return None


def require_secret(secret_name: str, env_var: str | None = None) -> str:
    """Like ``load_secret`` but raises when the credential is missing --
    for the handful of credentials whose absence is a deployment error rather
    than an optional feature."""
    value = load_secret(secret_name, env_var)
    if not value:
        raise RuntimeError(
            f"secret {secret_name!r} not found: mount it under {secrets_dir() / secret_name!s} "
            f"or set {env_var or secret_name}"
        )
    return value
