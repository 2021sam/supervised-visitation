"""Persistent, deduplicated provider leads and county extraction counts."""

import re
from datetime import datetime, timezone
from pathlib import Path


FIELDS = [
    "provider_name",
    "phone",
    "email",
    "website",
    "city",
    "source_url",
    "verification_status",
]


def _value(record, *keys):
    for key in keys:
        value = record.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _normalize(record):
    fields = record.get("fields") or {}

    if not isinstance(fields, dict):
        fields = {}

    name = _value(
        record, "provider_name", "name", "agency", "organization"
    ) or _value(
        fields, "provider_name", "name", "agency", "organization"
    )

    # Sonoma's PDF extractor stores provider names in contact lines.
    if not name:
        contact = fields.get("contact") or []
        if isinstance(contact, list) and contact:
            name = str(contact[0]).strip()

    phone = _value(record, "phone", "telephone") or _value(
        fields, "phone", "telephone"
    )

    contact = fields.get("contact") or []
    raw_lines = fields.get("raw_lines") or []

    lines = []
    for group in (contact, raw_lines):
        if isinstance(group, list):
            lines.extend(str(item) for item in group)

    if not phone:
        for line in lines:
            match = re.search(
                r"(?<!\d)(?:\+1[\s.-]?)?\(?\d{3}\)?"
                r"[\s.-]?\d{3}[\s.-]?\d{4}(?!\d)",
                line,
            )
            if match:
                phone = match.group(0)
                break

    email = _value(record, "email") or _value(fields, "email")

    if not email:
        for index, line in enumerate(lines):
            # PDF table cells sometimes split an email across lines.
            candidates = [line]
            if index + 1 < len(lines):
                candidates.append(line + lines[index + 1])

            for candidate in candidates:
                match = re.search(
                    r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
                    candidate,
                )
                if match:
                    email = match.group(0)
                    break

            if email:
                break

    return {
        "provider_name": name,
        "phone": phone,
        "email": email,
        "website": _value(record, "website", "url")
                   or _value(fields, "website", "url"),
        "city": _value(record, "city", "location")
                or _value(fields, "city", "location"),
        "source_url": _value(record, "source_url", "source"),
        "verification_status": _value(
            record, "verification_status"
        ) or "court_published_unverified",
    }



def normalized_provider_identity(record):
    """Return a comparable (provider name, source URL) identity.

    Uses the same field normalization as persisted provider leads,
    including names nested in PDF contact lines.
    """
    normalized = _normalize(record)
    name = normalized["provider_name"].strip().casefold()
    source_url = normalized["source_url"].strip()

    if not name or not source_url:
        return None

    return (name, source_url)


def _identity(record):
    name = record["provider_name"].casefold().strip()
    phone = "".join(c for c in record["phone"] if c.isdigit())
    email = record["email"].casefold().strip()

    if not name:
        return None

    return (name, phone or email)


def persist_county_leads(*, root, state, county, acquired, status_path=None):
    """Persist validated directory providers in SQLite using integer IDs."""
    from acquisition.search_first.search_cache import SearchCache

    db = SearchCache(
        Path(root) / "runs" / "search_first" / "search_cache.sqlite"
    )

    try:
        con = db.con
        timestamp = datetime.now(timezone.utc).isoformat()

        with con:
            con.execute(
                """
                INSERT INTO counties (state, county, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(state, county)
                DO UPDATE SET updated_at = excluded.updated_at
                """,
                (state, county, timestamp),
            )

            county_id = con.execute(
                "SELECT id FROM counties WHERE state = ? AND county = ?",
                (state, county),
            ).fetchone()[0]

            previous_count = con.execute(
                "SELECT COUNT(*) FROM providers WHERE county_id = ?",
                (county_id,),
            ).fetchone()[0]

            extracted_count = 0

            for document in acquired:
                if not document.get("directory_validated"):
                    continue

                source_url = (
                    document.get("source_url")
                    or document.get("candidate_url")
                    or document.get("url")
                )

                if not source_url:
                    continue

                normalized_records = []

                for raw in document.get("records", []):
                    record = dict(raw)
                    record["source_url"] = source_url
                    normalized = _normalize(record)

                    if _identity(normalized) is not None:
                        normalized_records.append(normalized)

                if not normalized_records:
                    continue

                extracted_count += len(normalized_records)

                con.execute(
                    """
                    INSERT INTO documents (
                        county_id, source_url, directory_validated,
                        validation_status
                    )
                    VALUES (?, ?, 1, 'validated')
                    ON CONFLICT(county_id, source_url)
                    DO UPDATE SET
                        directory_validated = 1,
                        validation_status = 'validated'
                    """,
                    (county_id, source_url),
                )

                document_id = con.execute(
                    """
                    SELECT id FROM documents
                    WHERE county_id = ? AND source_url = ?
                    """,
                    (county_id, source_url),
                ).fetchone()[0]

                for record in normalized_records:
                    existing = con.execute(
                        """
                        SELECT id, phone, email, website, city,
                               verification_status
                        FROM providers
                        WHERE document_id = ?
                          AND provider_name = ? COLLATE NOCASE
                        """,
                        (document_id, record["provider_name"]),
                    ).fetchone()

                    if existing:
                        provider_id, phone, email, website, city, status = existing

                        con.execute(
                            """
                            UPDATE providers
                            SET phone = ?, email = ?, website = ?,
                                city = ?, verification_status = ?
                            WHERE id = ?
                            """,
                            (
                                record["phone"] or phone,
                                record["email"] or email,
                                record["website"] or website,
                                record["city"] or city,
                                record["verification_status"] or status,
                                provider_id,
                            ),
                        )
                    else:
                        con.execute(
                            """
                            INSERT INTO providers (
                                county_id, document_id, provider_name,
                                phone, email, website, city,
                                verification_status
                            )
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                county_id,
                                document_id,
                                record["provider_name"],
                                record["phone"],
                                record["email"],
                                record["website"],
                                record["city"],
                                record["verification_status"],
                            ),
                        )

                document_count = con.execute(
                    "SELECT COUNT(*) FROM providers WHERE document_id = ?",
                    (document_id,),
                ).fetchone()[0]

                con.execute(
                    "UPDATE documents SET provider_count = ? WHERE id = ?",
                    (document_count, document_id),
                )

            total_count = con.execute(
                "SELECT COUNT(*) FROM providers WHERE county_id = ?",
                (county_id,),
            ).fetchone()[0]

            con.execute(
                """
                UPDATE counties
                SET provider_count = ?, updated_at = ?
                WHERE id = ?
                """,
                (total_count, timestamp, county_id),
            )

        return {
            "providers_extracted": extracted_count,
            "provider_lead_count": total_count,
            "providers_new": total_count - previous_count,
        }
    finally:
        db.con.close()


def get_saved_provider_identities(*, root, state, county):
    """Return persisted (provider name, source URL) identities."""
    from acquisition.search_first.search_cache import SearchCache

    db = SearchCache(
        Path(root) / "runs" / "search_first" / "search_cache.sqlite"
    )

    try:
        rows = db.con.execute(
            """
            SELECT p.provider_name, d.source_url
            FROM providers AS p
            JOIN documents AS d ON d.id = p.document_id
            JOIN counties AS c ON c.id = p.county_id
            WHERE c.state = ? AND c.county = ?
              AND d.directory_validated = 1
            """,
            (state, county),
        ).fetchall()

        return {
            (name.strip().casefold(), url.strip())
            for name, url in rows
        }
    finally:
        db.con.close()
