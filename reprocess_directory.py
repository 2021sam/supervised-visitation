"""Preview enrichment of a previously validated directory."""

import argparse
import sqlite3

from acquisition.database.validated_document import (
    get_validated_document,
)
from acquisition.database.supervisor_writer import (
    save_supervisor,
)
from acquisition.extraction.supervisor_details import (
    enrich_supervisor,
)
from readers.pdf_reader import extract


def preview(result_id):
    source = sqlite3.connect(
        "file:registry.db?mode=ro", uri=True
    )

    conn = sqlite3.connect(":memory:")
    source.backup(conn)
    source.close()

    try:
        conn.execute("PRAGMA foreign_keys=ON")

        court_id, county, url = conn.execute("""
            SELECT r.court_id, c.county, r.url
            FROM search_results r
            JOIN courts c ON c.court_id = r.court_id
            WHERE r.result_id = ?
              AND r.validation_status = 'VALIDATED'
        """, (result_id,)).fetchone()

        content, document_source = get_validated_document(
            conn, result_id
        )

        before = {
            row[0]
            for row in conn.execute(
                "SELECT supervisor_id FROM supervisors "
                "WHERE result_id = ?",
                (result_id,),
            )
        }

        print(f"County: {county}", flush=True)
        print(f"Document source: {document_source}", flush=True)
        print(f"Existing supervisors: {len(before)}", flush=True)
        print("Extracting PDF...", flush=True)

        records = extract(content, source_url=url)
        persisted = set()

        for candidate in records:
            record = enrich_supervisor(candidate)

            supervisor_id = save_supervisor(
                conn,
                court_id,
                result_id,
                record,
                original_name=candidate.get("name"),
            )

            if supervisor_id in persisted:
                raise ValueError("Duplicate supervisor identity")

            persisted.add(supervisor_id)

        print("\nPREVIEW RESULTS")
        print("=" * 50)
        print("Extracted:", len(records))
        print("Preserved IDs:", len(before & persisted))
        print("New IDs:", len(persisted - before))
        print("Unmatched existing IDs:", len(before - persisted))

        print("\nFIELD COVERAGE")

        for field in (
            "zip_code",
            "service_area",
            "service_counties",
            "languages",
            "additional_info",
        ):
            count = conn.execute(
                f"SELECT COUNT(*) FROM supervisors "
                f"WHERE result_id = ? AND TRIM({field}) != ''",
                (result_id,),
            ).fetchone()[0]

            print(f"{field:20} {count}")

        print("\nIdentity check:",
              "PASS" if before == persisted else "REVIEW REQUIRED")

    finally:
        conn.close()

    print("Live database unchanged.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--result-id", type=int, required=True)
    args = parser.parse_args()
    preview(args.result_id)
