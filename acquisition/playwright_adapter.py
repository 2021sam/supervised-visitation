"""Secondary browser discovery using Playwright."""

import asyncio
from urllib.parse import urljoin, urldefrag, urlparse

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

from .core import safe_public_url
from .discovery_registry import DiscoveryRegistry


async def _discover(url):
    """Render a page and extract same-host hyperlinks."""
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)

        try:
            page = await browser.new_page()
            await page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=30000,
            )

            final_url = page.url
            html = await page.content()
        finally:
            await browser.close()

    return final_url, html


def discover_with_playwright(
    url, *, registry_path, timeout_seconds=30
):
    """Persist Playwright discoveries in the shared registry."""
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")

    safe_public_url(url)

    async def bounded_discovery():
        return await asyncio.wait_for(
            _discover(url),
            timeout=timeout_seconds,
        )

    final_url, html = asyncio.run(bounded_discovery())
    safe_public_url(final_url)

    expected_host = urlparse(url).hostname

    if urlparse(final_url).hostname != expected_host:
        raise ValueError("Playwright redirected outside the court hostname")

    registry = DiscoveryRegistry(registry_path)
    soup = BeautifulSoup(html, "html.parser")

    saved = 0
    seen = set()

    for anchor in soup.select("a[href]"):
        href = anchor.get("href", "").strip()
        target, _ = urldefrag(urljoin(final_url, href))

        parsed = urlparse(target)

        if parsed.scheme not in {"http", "https"}:
            continue

        if parsed.hostname != expected_host:
            continue

        if target in seen:
            continue

        seen.add(target)
        safe_public_url(target)

        registry.add(
            target,
            extractor="playwright",
            found_on=final_url,
            link_text=anchor.get_text(" ", strip=True),
        )
        saved += 1

    return {
        "source_url": final_url,
        "engine": "playwright",
        "links_saved": saved,
        "total_unique_links": len(registry.data["links"]),
    }
