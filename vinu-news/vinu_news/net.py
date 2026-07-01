"""HTTP helper: retries a loopback URL via host.docker.internal.

.env is shared between local runs (where 127.0.0.1/localhost reaches
sibling services directly) and Docker Compose (where loopback means the
container itself). Rather than maintaining separate .env files per
environment, retry once against host.docker.internal when the configured
loopback host refuses the connection.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit, urlunsplit

import requests

_LOOPBACK_HOSTS = {"localhost", "127.0.0.1"}


def _docker_fallback_url(url: str) -> str | None:
    parts = urlsplit(url)
    if parts.hostname not in _LOOPBACK_HOSTS:
        return None
    netloc = "host.docker.internal"
    if parts.port:
        netloc = f"{netloc}:{parts.port}"
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))


def request(method: str, url: str, **kwargs: Any) -> requests.Response:
    """requests.request(), retried against host.docker.internal if `url`
    points at a loopback host that refuses the connection."""
    try:
        return requests.request(method, url, **kwargs)
    except requests.ConnectionError:
        fallback_url = _docker_fallback_url(url)
        if fallback_url is None:
            raise
        return requests.request(method, fallback_url, **kwargs)
