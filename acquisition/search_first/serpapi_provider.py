"""Database-first Google Search discovery through SerpAPI."""

import json
import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import httpx

from acquisition.search_first.search_cache import (
    SearchCache,
    cache_key,
)

SERPAPI_ENDPOINT = "https://serpapi.com/search.json"

DEFAULT_CACHE_PATH = (
    Path(__file__).resolve().parents[3]
    / "runs"
    / "search_first"
    / "search_cache.sqlite"
)


@dataclass(frozen=True)
class SearchResult:
    url: str
    title: str
    snippet: str
    query: str
    position: int
    provider: str = "serpapi"


class SearchAlreadyClaimed(RuntimeError):
    """Another worker owns this search, or a prior claim needs review."""


class SerpApiProvider:
    """Google Search provider with persistent historical snapshots."""

    def __init__(self, api_key=None, cache_path=None):
        self.api_key = (
            api_key
            if api_key is not None
            else os.environ.get("SERPAPI_API_KEY")
        )
        self.cache_path = Path(cache_path or DEFAULT_CACHE_PATH)

    def search(
        self,
        query: str,
        *,
        site: str | None = None,
        refresh: bool = False,
    ) -> list[SearchResult]:
        """Search Google, reusing cached results unless refresh is requested."""

        if site:
            parsed = urlparse(site)

            if parsed.scheme != "https" or not parsed.hostname:
                raise ValueError("site must be an HTTPS URL")

            query = f"site:{parsed.hostname} {query}"

        parameters = {
            "engine": "google",
            "q": query,
            "udm": "web",
        }

        cache = SearchCache(self.cache_path)

        try:
            key = cache_key("serpapi", query, parameters)

            payload = None if refresh else cache.get(key)

            if payload is None:
                key, claimed = cache.claim(
                    "serpapi",
                    query,
                    parameters,
                    refresh=refresh,
                )

                if not claimed:
                    if refresh:
                        raise SearchAlreadyClaimed(
                            f"Refresh already claimed: {query}"
                        )

                    payload = cache.get(key)

                    if payload is None:
                        raise SearchAlreadyClaimed(
                            f"Search already claimed: {query}"
                        )

                if payload is None:
                    if not self.api_key:
                        cache.record_failure(
                            key,
                            "SERPAPI_API_KEY is not configured",
                        )
                        raise ValueError(
                            "SERPAPI_API_KEY is required for uncached searches"
                        )

                    try:
                        response = httpx.get(
                            SERPAPI_ENDPOINT,
                            params={
                                **parameters,
                                "api_key": self.api_key,
                            },
                            timeout=30,
                            follow_redirects=False,
                        )

                        response.raise_for_status()

                        raw_json = response.content
                        payload = json.loads(raw_json)

                        if not isinstance(payload, dict):
                            raise ValueError(
                                "SerpAPI response must be a JSON object"
                            )

                        if payload.get("error"):
                            raise RuntimeError(str(payload["error"]))

                        # Preserve the exact original response bytes
                        # before extracting individual search results.
                        cache.save(key, raw_json)

                    except Exception as exc:
                        cache.record_failure(key, exc)
                        raise

            results = []

            for index, item in enumerate(
                payload.get("organic_results", []),
                start=1,
            ):
                url = item.get("link")

                if not url:
                    continue

                results.append(
                    SearchResult(
                        url=url,
                        title=item.get("title", ""),
                        snippet=item.get("snippet", ""),
                        query=query,
                        position=item.get("position", index),
                    )
                )

            return results

        finally:
            cache.close()
