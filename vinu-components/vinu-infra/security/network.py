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
    """Rejects a URL whose hostname is *literally* localhost/private/link-
    local -- catches the common case (a caller-supplied URL that directly
    names an internal address).

    Real, NOT-fixed-here gap: this never resolves DNS. A hostname that
    resolves to a private/internal address (DNS rebinding -- e.g. a domain
    an attacker controls that answers with 10.x.x.x) is not an `ipaddress`-
    parseable literal, so it falls through the private-network check
    entirely and this returns True. Closing that gap properly needs
    connect-time validation (checking the socket's actual resolved address,
    with defense against the answer changing between check and connect),
    not a stronger string check here -- deliberately left as a known,
    documented limitation rather than a shallow patch that would look like
    a real fix without being one.
    """
    try:
        parsed = urlparse(url)
        host = parsed.hostname
        if host is None:
            return False

        if host in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
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
