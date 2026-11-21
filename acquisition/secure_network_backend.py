"""Network backend that connects only to validated public IPs."""

import ipaddress
import socket

from httpcore import SyncBackend


class PublicNetworkBackend(SyncBackend):
    """Resolve, validate, and connect to a public IP address."""

    def connect_tcp(
        self,
        host,
        port,
        timeout=None,
        local_address=None,
        socket_options=None,
    ):
        hostname = (
            host.decode("ascii")
            if isinstance(host, bytes)
            else host
        )

        addresses = socket.getaddrinfo(
            hostname,
            port,
            type=socket.SOCK_STREAM,
        )

        if not addresses:
            raise ValueError("Hostname resolved to no addresses")

        validated = []

        for address in addresses:
            ip = ipaddress.ip_address(address[4][0])

            if not ip.is_global:
                raise ValueError(
                    f"Non-public network destination: {ip}"
                )

            validated.append(str(ip))

        # Use the validated numeric IP, not the original hostname.
        # This prevents a second DNS lookup from changing the target.
        return super().connect_tcp(
            host=validated[0],
            port=port,
            timeout=timeout,
            local_address=local_address,
            socket_options=socket_options,
        )
