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

from readers.pdf_reader import extract as extract_pdf


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
            for record in records:
                name = str(record.get("name") or "").strip()
                phones = record.get("phones") or []
                emails = record.get("emails") or []

                phone = str(
                    record.get("phone") or (phones[0] if phones else "")
                ).strip()
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

                valid_phone = (
                    len(re.sub(r"\D", "", phone)) in (10, 11)
                    and (
                        len(re.sub(r"\D", "", phone)) == 10
                        or re.sub(r"\D", "", phone).startswith("1")
                    )
                )

                valid_email = bool(re.fullmatch(
                    r"[^\s@]+@[^\s@]+\.[^\s@]+",
                    email,
                ))

                if not (valid_phone or valid_email):
                    continue

                con.execute("""
                    INSERT OR IGNORE INTO supervisors
                    (court_id, result_id, name, phone,
                     email, website, raw_text)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    court_id,
                    result_id,
                    name,
                    phone if valid_phone else "",
                    email if valid_email else "",
                    record.get("website") or "",
                    record.get("raw_text") or "",
                ))

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
                SET classification = 'FOUND'
                WHERE court_id = ?
                  AND EXISTS (
                      SELECT 1
                      FROM supervisors
                      WHERE court_id = ?
                        AND result_id = ?
                  )
            """, (court_id, court_id, result_id))

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
