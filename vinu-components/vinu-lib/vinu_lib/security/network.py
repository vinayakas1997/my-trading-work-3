from __future__ import annotations

import ipaddress
from urllib.parse import urlparse


_PRIVATE_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]


def validate_url_target(url: str) -> bool:
    try:
        parsed = urlparse(url)
        host = parsed.hostname
        if host is None:
            return False

        if host in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
            return False

        if host.startswith("10.") or host.startswith("172.16.") or host.startswith("192.168."):
            return False

        try:
            addr = ipaddress.ip_address(host)
            for net in _PRIVATE_NETWORKS:
                if addr in net:
                    return False
        except ValueError:
            pass

        return True
    except (ValueError, AttributeError):
        return False
