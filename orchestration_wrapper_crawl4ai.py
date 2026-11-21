"""Orchestrate Crawl4AI discovery, directory validation and persistence."""

import argparse
import json
import sqlite3
from pathlib import Path
from urllib.parse import urlparse

from crawl4ai_search import search
from directory_validator import validate


ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "registry.db"

QUERY = "family services supervised visitation"

LINK_FILTER = [
    "supervised visitation",
    "supervised visit",
    "family court services",
    "family services",
    "community resources",
]


def persist_candidates(connection, court_id, query, candidates):
    registered = []

    with connection:
        for candidate in candidates:
            connection.execute(
                """
                INSERT OR IGNORE INTO search_results
                (court_id, query, title, url, snippet)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    court_id,
                    query,
                    candidate["text"],
                    candidate["url"],
                    json.dumps(candidate),
                ),
            )

            result_id, status = connection.execute(
                """
                SELECT result_id, validation_status
                FROM search_results
                WHERE court_id = ? AND url = ?
                """,
                (court_id, candidate["url"]),
            ).fetchone()

            registered.append({
                **candidate,
                "result_id": result_id,
                "validation_status": status,
            })

    return registered


def provider_count(connection, court_id):
    return connection.execute(
        """
        SELECT COUNT(*)
        FROM supervisors
        WHERE court_id = ?
        """,
        (court_id,),
    ).fetchone()[0]


def validate_candidates(connection, court_id, candidates):
    for candidate in candidates:
        if not candidate["document"]:
            continue

        if not urlparse(candidate["url"]).path.lower().endswith(".pdf"):
            continue

        if candidate["validation_status"] in (
            "REJECTED",
            "VALIDATED",
        ):
            continue

        result_id = candidate["result_id"]

        print(f"\n[VALIDATE] {candidate['url']}", flush=True)

        try:
            validate(result_id)

        except Exception as exc:
            status = (
                "REJECTED"
                if isinstance(exc, ValueError)
                else "EXTRACTION_FAILED"
            )

            with connection:
                connection.execute(
                    """
                    UPDATE search_results
                    SET validation_status = ?,
                        rejection_reason = ?,
                        validated_at = CURRENT_TIMESTAMP
                    WHERE result_id = ?
                    """,
                    (status, str(exc), result_id),
                )

            print(f"[{status}] {exc}", flush=True)
            continue

        classification = connection.execute(
            """
            SELECT classification FROM courts
            WHERE court_id = ?
            """,
            (court_id,),
        ).fetchone()[0]

        count = provider_count(connection, court_id)

        if classification == "FOUND" and count > 0:
            print(
                f"\n[EARLY EXIT] {count} providers saved.",
                flush=True,
            )
            return True

    return False


def run(args):
    connection = sqlite3.connect(DB_PATH, timeout=30)
    connection.execute("PRAGMA foreign_keys=ON")

    try:
        row = connection.execute(
            """
            SELECT county, classification
            FROM courts
            WHERE court_id = ?
            """,
            (args.court_id,),
        ).fetchone()

        if row is None:
            raise ValueError(f"Unknown court_id: {args.court_id}")

        county, classification = row

        print(f"Court: {county} ({args.court_id})")
        print(f"Classification: {classification}")

        if classification == "MIA":
            print("[SKIP] County classified MIA.")
            return

        if (
            classification == "FOUND"
            and provider_count(connection, args.court_id) > 0
        ):
            print("[SKIP] County already validated.")
            return

        # Stage 1: Discover candidate links.
        results = search(
            url=args.url,
            query=args.query,
            strategy="best-first",
            ranking="hybrid",
            max_depth=args.max_depth,
            max_pages=args.max_pages,
            extract_documents=False,
            link_filter=LINK_FILTER,
        )

        print(f"\nPages visited: {results['pages_visited']}")
        print(f"Candidates: {results['candidate_count']}")

        # Stage 2: Persist discovery evidence.
        candidates = persist_candidates(
            connection,
            args.court_id,
            args.query,
            results["candidates"],
        )

        # Stage 3: Validate ranked PDF candidates.
        validate_candidates(
            connection,
            args.court_id,
            candidates,
        )

        # Stage 4: Report the persisted outcome.
        classification = connection.execute(
            """
            SELECT classification FROM courts
            WHERE court_id = ?
            """,
            (args.court_id,),
        ).fetchone()[0]

        print("\n=== FINAL RESULT ===")
        print(f"County: {county}")
        print(f"Classification: {classification}")
        print(f"Providers: {provider_count(connection, args.court_id)}")

    finally:
        connection.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Crawl4AI registry orchestration wrapper"
    )

    parser.add_argument("--court-id", type=int, required=True)
    parser.add_argument("--url", required=True)
    parser.add_argument("--query", default=QUERY)
    parser.add_argument("--max-depth", type=int)
    parser.add_argument("--max-pages", type=int)

    run(parser.parse_args())
