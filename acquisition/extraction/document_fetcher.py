"""Download official court documents for the acquisition pipeline."""

import httpx

from ..secure_transport import SecureCourtTransport
from urllib.parse import urljoin, urlsplit

MAX_DOCUMENT_BYTES = 20 * 1024 * 1024

from ..core import safe_public_url


def fetch_document(url: str) -> tuple[str, str, bytes]:
    """Fetch a document and return its final URL, content type, and bytes."""
    safe_public_url(url)
    original_host = urlsplit(url).hostname

    with httpx.Client(
        transport=SecureCourtTransport(),
        follow_redirects=False,
        trust_env=False,
        timeout=30,
    ) as client:
        current_url = url

        for _ in range(6):
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

                    if urlsplit(next_url).hostname != original_host:
                        raise ValueError(
                            "Redirect outside authorized court hostname"
                        )

                    current_url = next_url
                    continue

                if response.status_code == 403:
                    from .browser_fetcher import fetch_html_with_browser
                    return fetch_html_with_browser(current_url)

                response.raise_for_status()

                declared_size = response.headers.get(
                    "content-length"
                )

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
                        raise ValueError(
                            "Document exceeds size limit"
                        )

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
