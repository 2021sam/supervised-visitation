"""Browser-based acquisition of publicly accessible court HTML documents."""

from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright

from ..core import safe_public_url

MAX_HTML_BYTES = 20 * 1024 * 1024


def fetch_html_with_browser(url: str) -> tuple[str, str, bytes]:
    """Fetch HTML through visible Chromium and return URL, MIME type, bytes."""
    safe_public_url(url)

    original_host = urlsplit(url).hostname

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)

        try:
            page = browser.new_page()

            response = page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=30000,
            )

            if response is None or response.status != 200:
                raise RuntimeError(
                    f"Browser acquisition failed: "
                    f"HTTP {response.status if response else 'unknown'}"
                )

            final_url = page.url
            safe_public_url(final_url)

            if urlsplit(final_url).hostname != original_host:
                raise ValueError("Browser redirected outside court hostname")

            html = page.content().encode("utf-8")

            if len(html) > MAX_HTML_BYTES:
                raise ValueError("HTML exceeds size limit")

            return final_url, "text/html; charset=utf-8", html

        finally:
            browser.close()
