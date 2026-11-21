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



def build_search_url(court_url, query):
    """Append the court's internal search endpoint."""
    from urllib.parse import urlsplit, urlunsplit, quote_plus

    parts = urlsplit(court_url.strip())

    if parts.scheme not in ("http", "https") or not parts.netloc:
        raise ValueError(f"Invalid court URL: {court_url}")

    return urlunsplit((
        parts.scheme,
        parts.netloc,
        "/search",
        "search=" + quote_plus(query),
        "",
    ))


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

        if candidate["validation_status"] in ("REJECTED", "VALIDATED"):
            continue

        result_id = candidate["result_id"]
        print(f"\\n[VALIDATE] {candidate['url']}", flush=True)

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

        count = provider_count(connection, court_id)
        validated = connection.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM search_results
                WHERE result_id = ?
                  AND court_id = ?
                  AND validation_status = 'VALIDATED'
            )
            """,
            (result_id, court_id),
        ).fetchone()[0]

        if validated and count > 0:
            with connection:
                connection.execute(
                    "UPDATE courts SET FOUND = 1 WHERE court_id = ? AND MIA = 0",
                    (court_id,),
                )
            print(f"\\n[EARLY EXIT] {count} providers saved.", flush=True)
            return True

    return False


def run(args):
    connection = sqlite3.connect(DB_PATH, timeout=30)
    connection.execute("PRAGMA foreign_keys=ON")

    run_id = None
    pages_visited = 0
    candidates_found = 0

    try:
        row = connection.execute(
            """
            SELECT county, FOUND, MIA
            FROM courts
            WHERE court_id = ?
            """,
            (args.court_id,),
        ).fetchone()

        if row is None:
            raise ValueError(f"Unknown court_id: {args.court_id}")

        county, found, mia = row
        print(f"Court: {county} ({args.court_id})")
        print(f"FOUND: {found} | MIA: {mia}")

        if not args.force and (found or mia):
            print("[SKIP] County already FOUND or manually MIA.")
            return

        with connection:
            cursor = connection.execute(
                """
                INSERT INTO county_search_runs (court_id)
                VALUES (?)
                """,
                (args.court_id,),
            )
            run_id = cursor.lastrowid

        start_url = (
            build_search_url(args.url, args.query)
            if args.append_search
            else args.url
        )

        print(f"Starting URL: {start_url}", flush=True)

        results = search(
            url=start_url,
            query=args.query,
            strategy="best-first",
            ranking="hybrid",
            max_depth=args.max_depth,
            max_pages=args.max_pages,
            extract_documents=False,
            link_filter=None,
        )

        pages_visited = results["pages_visited"]
        candidates_found = results["candidate_count"]

        print(f"\\nPages visited: {pages_visited}")
        print(f"Candidates: {candidates_found}")

        candidates = persist_candidates(
            connection, args.court_id, args.query, results["candidates"]
        )

        validate_candidates(connection, args.court_id, candidates)

        found, mia = connection.execute(
            "SELECT FOUND, MIA FROM courts WHERE court_id = ?",
            (args.court_id,),
        ).fetchone()

        outcome = "FOUND" if found else "NOT_FOUND"

        with connection:
            connection.execute(
                """
                UPDATE county_search_runs
                SET completed_at = CURRENT_TIMESTAMP,
                    result = ?,
                    pages_visited = ?,
                    candidates_found = ?
                WHERE run_id = ?
                """,
                (outcome, pages_visited, candidates_found, run_id),
            )

        print("\\n=== FINAL RESULT ===")
        print(f"County: {county}")
        print(f"FOUND: {found} | MIA: {mia}")
        print(f"Search result: {outcome}")
        print(f"Providers: {provider_count(connection, args.court_id)}")

    except Exception as exc:
        if run_id is not None:
            with connection:
                connection.execute(
                    """
                    UPDATE county_search_runs
                    SET completed_at = CURRENT_TIMESTAMP,
                        result = 'ERROR',
                        pages_visited = ?,
                        candidates_found = ?,
                        error_message = ?
                    WHERE run_id = ?
                    """,
                    (pages_visited, candidates_found, str(exc), run_id),
                )
        raise

    finally:
        connection.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Crawl4AI registry orchestration wrapper"
    )
    parser.add_argument("--court-id", type=int)
    parser.add_argument("--url")
    parser.add_argument(
        "--all",
        action="store_true",
        help="Search all eligible courts from SQLite",
    )
    parser.add_argument(
        "--append-search",
        action="store_true",
        help="Append the supervised visitation search path to the court URL",
    )
    parser.add_argument("--query", default=QUERY)
    parser.add_argument("--max-depth", type=int)
    parser.add_argument("--max-pages", type=int)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Explicitly search a FOUND or manually MIA county",
    )
    args = parser.parse_args()

    if args.court_id is not None:
        # Single-court mode.
        if args.all:
            parser.error("--all cannot be combined with --court-id")

        if args.url is None:
            with sqlite3.connect(DB_PATH) as connection:
                row = connection.execute(
                    "SELECT court_url FROM courts WHERE court_id = ?",
                    (args.court_id,),
                ).fetchone()

            if row is None:
                parser.error(f"Unknown court_id: {args.court_id}")

            args.url = row[0]

        run(args)

    else:
        # Batch mode: no court ID means all eligible courts.
        if args.url is not None:
            parser.error("--url requires --court-id")

        with sqlite3.connect(DB_PATH) as connection:
            courts = connection.execute(
                """
                SELECT court_id, county, court_url
                FROM courts
                WHERE FOUND = 0 AND MIA = 0
                ORDER BY court_id
                """
            ).fetchall()

        print(f"\\nEligible courts: {len(courts)}", flush=True)

        completed = 0
        errors = 0

        for index, (court_id, county, court_url) in enumerate(courts, 1):
            print(
                f"\\n=== COURT {index}/{len(courts)}: {county} ===",
                flush=True,
            )

            if not court_url:
                print(f"[ERROR] Missing court URL: {county}", flush=True)
                errors += 1
                continue

            court_args = argparse.Namespace(
                **{
                    **vars(args),
                    "court_id": court_id,
                    "url": court_url,
                    "force": False,
                }
            )

            try:
                run(court_args)
                completed += 1
            except Exception as exc:
                errors += 1
                print(f"[ERROR] {county}: {exc}", flush=True)
                print("[CONTINUE] Moving to next county.", flush=True)

        print("\\n=== BATCH COMPLETE ===")
        print(f"Eligible courts: {len(courts)}")
        print(f"Completed without exception: {completed}")
        print(f"Errors: {errors}")
