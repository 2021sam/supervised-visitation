"""Discover California supervised-visitation directories using SerpAPI."""

import argparse
import json
import os
import sqlite3
from pathlib import Path

import httpx

from search_cache import SearchCache, cache_key

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "registry.db"
SERPAPI_ENDPOINT = "https://serpapi.com/search.json"


def search(query, cache):
    """Search Google, reusing a saved response when available."""
    parameters = {
        "engine": "google",
        "q": query,
        "udm": "web",
    }

    key = cache_key("serpapi", query, parameters)
    payload = cache.get(key)

    if payload is not None:
        return payload

    key, claimed = cache.claim("serpapi", query, parameters)

    if not claimed:
        payload = cache.get(key)
        if payload is not None:
            return payload
        raise RuntimeError(f"Search already claimed: {query}")

    try:
        api_key = os.environ.get("SERPAPI_API_KEY")
        if not api_key:
            raise ValueError("SERPAPI_API_KEY is not configured")

        response = httpx.get(
            SERPAPI_ENDPOINT,
            params={**parameters, "api_key": api_key},
            timeout=30,
            follow_redirects=False,
        )
        response.raise_for_status()

        raw_json = response.content
        payload = json.loads(raw_json)

        if not isinstance(payload, dict):
            raise ValueError("SerpAPI response must be a JSON object")

        if payload.get("error"):
            raise RuntimeError(str(payload["error"]))

        cache.save(key, raw_json)
        return payload

    except Exception as exc:
        cache.record_failure(key, exc)
        raise


def run(court_id=None):
    connection = sqlite3.connect(DB_PATH, timeout=30)
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("PRAGMA busy_timeout=30000")

    cache = SearchCache(DB_PATH)

    try:
        if court_id is None:
            courts = connection.execute(
                "SELECT court_id, county FROM courts ORDER BY court_id"
            ).fetchall()
        else:
            courts = connection.execute(
                "SELECT court_id, county FROM courts WHERE court_id = ?",
                (court_id,),
            ).fetchall()

        if not courts:
            raise ValueError("No matching court found")

        for current_id, county in courts:
            query = (
                f"{county} County California Superior Court "
                "supervised visitation provider list"
            )

            print(f"\n[{current_id}] {county}: {query}", flush=True)

            payload = search(query, cache)
            results = payload.get("organic_results", [])

            if not isinstance(results, list):
                raise ValueError("organic_results must be a list")

            added = 0

            with connection:
                for result in results:
                    if not isinstance(result, dict):
                        continue

                    url = result.get("link")
                    if not url:
                        continue

                    cursor = connection.execute(
                        """
                        INSERT OR IGNORE INTO search_results
                        (court_id, query, title, url, snippet)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            current_id,
                            query,
                            result.get("title", ""),
                            url,
                            result.get("snippet", ""),
                        ),
                    )
                    added += cursor.rowcount

            total = connection.execute(
                """
                SELECT COUNT(*)
                FROM search_results
                WHERE court_id = ?
                """,
                (current_id,),
            ).fetchone()[0]

            print(
                f"Returned: {len(results)} | "
                f"Added: {added} | "
                f"Court results in DB: {total}",
                flush=True,
            )

    finally:
        cache.close()
        connection.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Search for official supervised-visitation directories"
    )
    parser.add_argument(
        "--court-id",
        type=int,
        help="Search one court; omit to search all courts",
    )

    args = parser.parse_args()
    run(args.court_id)
