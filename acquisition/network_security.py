"""Network destination validation for public court acquisition."""

import ipaddress
import socket
from urllib.parse import urlsplit

from .core import safe_public_url


def validate_public_destination(url: str) -> str:
    """Reject URLs resolving to non-global IP addresses."""
    safe_public_url(url)

    hostname = urlsplit(url).hostname

    if not hostname:
        raise ValueError("URL hostname is required")

    try:
        addresses = socket.getaddrinfo(
            hostname,
            None,
            type=socket.SOCK_STREAM,
        )
    except socket.gaierror as exc:
        raise ValueError(
            f"Unable to resolve hostname: {hostname}"
        ) from exc

    if not addresses:
        raise ValueError("Hostname resolved to no addresses")

    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])

        if not ip.is_global:
            raise ValueError(
                f"Non-public network destination: {ip}"
            )

    return url
