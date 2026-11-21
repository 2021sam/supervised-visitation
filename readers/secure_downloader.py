"""Secure, reusable HTTP document downloader."""

import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import httpx

ENGINE_ROOT = Path.home() / "apps/data-acquisition-engine"

if str(ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(ENGINE_ROOT))

from acquisition.core import safe_public_url
from acquisition.secure_transport import SecureCourtTransport

MAX_DOCUMENT_BYTES = 20 * 1024 * 1024
MAX_REDIRECTS = 5


def download_document(url: str) -> tuple[str, str, bytes]:
    """Return final URL, content type, and document bytes."""

    safe_public_url(url)
    original_host = urlsplit(url).hostname.lower()

    with httpx.Client(
        transport=SecureCourtTransport(),
        follow_redirects=False,
        trust_env=False,
        timeout=30,
    ) as client:

        current_url = url

        for _ in range(MAX_REDIRECTS + 1):
            safe_public_url(current_url)

            with client.stream("GET", current_url) as response:

                if response.is_redirect:
                    location = response.headers.get("location")

                    if not location:
                        raise ValueError(
                            "Redirect missing Location header"
                        )

                    next_url = urljoin(current_url, location)
                    safe_public_url(next_url)

                    if urlsplit(next_url).hostname.lower() != original_host:
                        raise ValueError(
                            "Redirect outside original hostname"
                        )

                    current_url = next_url
                    continue

                response.raise_for_status()

                declared_size = response.headers.get("content-length")

                if (
                    declared_size is not None
                    and int(declared_size) > MAX_DOCUMENT_BYTES
                ):
                    raise ValueError("Document exceeds size limit")

                chunks = []
                total = 0

                for chunk in response.iter_bytes():
                    total += len(chunk)

                    if total > MAX_DOCUMENT_BYTES:
                        raise ValueError("Document exceeds size limit")

                    chunks.append(chunk)

                return (
                    str(response.url),
                    response.headers.get(
                        "content-type",
                        "application/octet-stream",
                    ),
                    b"".join(chunks),
                )

    raise ValueError("Too many document redirects")
