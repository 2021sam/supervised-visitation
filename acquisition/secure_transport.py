"""HTTPX transport using a public-IP-only network backend."""

import httpcore
import httpx

from .secure_network_backend import PublicNetworkBackend


class SecureCourtTransport(httpx.HTTPTransport):
    """Direct HTTPS transport with validated TCP destinations."""

    def __init__(self):
        super().__init__(
            verify=True,
            trust_env=False,
            http1=True,
            http2=False,
        )

        # Preserve HTTPX's verified TLS context.
        ssl_context = self._pool._ssl_context

        # Close the default pool before replacing it.
        self._pool.close()

        self._pool = httpcore.ConnectionPool(
            ssl_context=ssl_context,
            network_backend=PublicNetworkBackend(),
            http1=True,
            http2=False,
            max_connections=10,
            max_keepalive_connections=5,
        )
