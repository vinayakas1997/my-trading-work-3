from __future__ import annotations

import logging
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

LOG = logging.getLogger(__name__)

_LOOPBACK_HOSTS = {"localhost", "127.0.0.1"}
_DOCKER_GATEWAY = "172.17.0.1"


def is_running_in_docker() -> bool:
    if Path("/.dockerenv").exists():
        return True
    cgroup = Path("/proc/1/cgroup")
    if cgroup.exists():
        try:
            content = cgroup.read_text()
            if "docker" in content or "kubepods" in content:
                return True
        except OSError:
            pass
    return False


def alternative_urls(configured_url: str) -> list[str]:
    """Return alternative URLs to try when the configured one fails in Docker.

    Returns [configured, *alternatives] so callers can try them in order.
    """
    parts = urlsplit(configured_url)
    if parts.hostname not in _LOOPBACK_HOSTS:
        return [configured_url]

    port = parts.port or (443 if parts.scheme == "https" else 80)

    candidates = [configured_url]
    if port:
        docker_int = urlunsplit((parts.scheme, f"host.docker.internal:{port}", parts.path, parts.query, parts.fragment))
        candidates.append(docker_int)
        docker_gw = urlunsplit((parts.scheme, f"{_DOCKER_GATEWAY}:{port}", parts.path, parts.query, parts.fragment))
        candidates.append(docker_gw)

    return candidates
