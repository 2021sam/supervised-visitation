"""Validate official court PDF directories and persist extracted providers."""

import argparse
import os
import re
import sqlite3
import sys
from pathlib import Path
from urllib.parse import urlparse

import httpx

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "registry.db"

from readers.pdf_reader import (
    extract as extract_pdf,
    extract_text as extract_pdf_text,
)

from acquisition.extraction.directory_sections import (
    has_provider_directory_heading,
)
from acquisition.extraction.contact_cleanup import (
    normalize_phone_numbers,
)
from acquisition.extraction.supervisor_details import (
    enrich_supervisor,
)
from acquisition.database.supervisor_schema import (
    ensure_supervisor_detail_columns,
)
from acquisition.database.validated_document import (
    save_validated_document,
)
from acquisition.database.supervisor_writer import (
    save_supervisor,
)



def validate(result_id):
    con = sqlite3.connect(DB_PATH, timeout=30)
    con.execute("PRAGMA foreign_keys=ON")

    try:
        row = con.execute("""
            SELECT r.court_id, c.county, c.court_url,
                   r.title, r.url
            FROM search_results r
            JOIN courts c ON c.court_id = r.court_id
            WHERE r.result_id = ?
        """, (result_id,)).fetchone()

        if row is None:
            raise ValueError(f"Unknown result_id: {result_id}")

        court_id, county, court_url, title, url = row

        print(f"Court: {county} ({court_id})")
        print(f"Result: {result_id}")
        print(f"PDF: {url}")

        response = httpx.get(
            url,
            timeout=60,
            follow_redirects=True,
        )
        response.raise_for_status()

        content = response.content

        if not content.startswith(b"%PDF-"):
            raise ValueError("Downloaded content is not a PDF")

        markdown = extract_pdf_text(content)

        if not has_provider_directory_heading(markdown):
            raise ValueError(
                "Document is not a recognized supervised-visitation "
                "provider directory"
            )

        records = extract_pdf(
            content,
            source_url=url,
        )

        print(f"Providers extracted: {len(records)}")

        if not records:
            raise ValueError(
                "No providers extracted; directory not validated"
            )

        con.execute("""
            CREATE TABLE IF NOT EXISTS supervisors (
                supervisor_id INTEGER PRIMARY KEY,
                court_id INTEGER NOT NULL
                    REFERENCES courts(court_id),
                result_id INTEGER NOT NULL
                    REFERENCES search_results(result_id),
                name TEXT NOT NULL,
                phone TEXT NOT NULL DEFAULT '',
                email TEXT NOT NULL DEFAULT '',
                website TEXT NOT NULL DEFAULT '',
                raw_text TEXT NOT NULL DEFAULT '',
                UNIQUE(result_id, name)
            )
        """)

        before = con.execute("""
            SELECT COUNT(*) FROM supervisors
            WHERE result_id = ?
        """, (result_id,)).fetchone()[0]

        with con:
            ensure_supervisor_detail_columns(con)
            persisted_ids = set()

            for candidate in records:
                original_name = str(
                    candidate.get("name") or ""
                ).strip()

                record = enrich_supervisor(candidate)
                name = str(record.get("name") or "").strip()
                phones = record.get("phones") or []
                emails = record.get("emails") or []

                phone = normalize_phone_numbers(
                    record.get("phone"), *phones
                )
                email = str(
                    record.get("email") or (emails[0] if emails else "")
                ).strip()

                # Reject document headings and administrative notices.
                invalid_names = {
                    "please note",
                    "professional supervised visitation providers",
                    "name of authorized provider",
                    "disclaimer",
                }

                normalized_name = name.casefold().strip(" :.-")

                is_court_heading = bool(re.search(
                    r"\b(?:superior court of california|"
                    r"superior court of the state of california|"
                    r"california superior court)\b",
                    normalized_name,
                ))

                if (
                    not name
                    or normalized_name in invalid_names
                    or is_court_heading
                ):
                    continue

                valid_phone = bool(phone)

                valid_email = bool(re.fullmatch(
                    r"[^\s@]+@[^\s@]+\.[^\s@]+",
                    email,
                ))

                if not (valid_phone or valid_email):
                    continue

                record["name"] = name
                record["phone"] = phone if valid_phone else ""
                record["email"] = email if valid_email else ""

                supervisor_id = save_supervisor(
                    con,
                    court_id,
                    result_id,
                    record,
                    original_name=original_name,
                )

                if supervisor_id in persisted_ids:
                    raise ValueError(
                        f"Duplicate supervisor identity: {name}"
                    )

                persisted_ids.add(supervisor_id)

            if not persisted_ids:
                raise ValueError("No valid supervisors persisted")

            after = con.execute("""
                SELECT COUNT(*) FROM supervisors
                WHERE result_id = ?
            """, (result_id,)).fetchone()[0]

            if after == 0:
                raise ValueError("No providers persisted")

            con.execute("""
                UPDATE search_results
                SET validation_status = 'VALIDATED',
                    rejection_reason = NULL,
                    validated_at = CURRENT_TIMESTAMP
                WHERE result_id = ?
            """, (result_id,))

            # A validated official directory with at least one
            # persisted provider qualifies the county as FOUND.
            con.execute("""
                UPDATE courts
                SET FOUND = 1
                WHERE court_id = ?
                  AND EXISTS (
                      SELECT 1
                      FROM supervisors
                      WHERE court_id = ?
                        AND result_id = ?
                  )
            """, (court_id, court_id, result_id))

        path = save_validated_document(result_id, content)
        print(f"PDF retained: {path}")

        print(f"Before: {before}")
        print(f"Added: {after - before}")
        print(f"After: {after}")
        print("Validation: VALIDATED")

    finally:
        con.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--result-id", type=int, required=True)
    args = parser.parse_args()
    validate(args.result_id)
