"""Extract professional supervised-visitation provider profile tables."""

import re

import pymupdf


FIELD_NAMES = {
    "location": "location",
    "phone": "phone",
    "phone/fax": "phone",
    "phone/ fax": "phone",
    "email": "email",
    "website": "website",
    "service area": "service_area",
    "language": "language",
    "languages": "language",
    "hours": "hours",
    "sliding scale": "sliding_scale",
    "rate": "rate",
    "provider services": "provider_services",
}

SERVICE_PATTERN = re.compile(
    r"\bsupervised\s+visitation\b"
    r"|\bsupervised\s+visits?\b"
    r"|\bsupervised\s+exchanges?\b"
    r"|\bsafe\s+exchanges?\b"
    r"|\bmonitored\s+exchanges?\b"
    r"|\bvisitation\s+(?:supervision|monitor(?:ing)?)\b"
    r"|\bvisitation\s+reports?\b",
    re.IGNORECASE,
)


def _clean(value):
    if value is None:
        return ""

    return " ".join(str(value).split()).strip()


def _field_name(value):
    return FIELD_NAMES.get(
        _clean(value).rstrip(":").strip().lower()
    )


def _parse_profile(rows):
    if len(rows) < 3:
        return None

    first = rows[0]

    if len(first) != 2:
        return None

    name = _clean(first[0])

    if not name or _clean(first[1]):
        return None

    if _field_name(name):
        return None

    fields = {}

    for row in rows[1:]:
        if len(row) != 2:
            continue

        key = _field_name(row[0])

        if not key:
            continue

        value = _clean(row[1])

        if value:
            fields[key] = value

    # Require evidence that this is a provider profile,
    # not an unrelated two-column PDF table.
    if not fields.get("phone"):
        return None

    # Service area is optional in some court-published profiles.
    # Do not infer a service area from the publishing county.
    if not fields.get("provider_services"):
        return None

    if not SERVICE_PATTERN.search(fields["provider_services"]):
        return None

    return {
        "name": name,
        **fields,
    }


def extract_pdf_provider_profiles(
    pdf_bytes,
    *,
    start_page=0,
    source_url=None,
):
    """Return unverified provider records with source provenance."""

    records = []

    with pymupdf.open(
        stream=pdf_bytes,
        filetype="pdf",
    ) as pdf:

        for page_index in range(start_page, len(pdf)):
            page = pdf[page_index]

            for table in page.find_tables().tables:
                if table.col_count != 2:
                    continue

                fields = _parse_profile(table.extract())

                if fields is None:
                    continue

                records.append({
                    "page": page_index + 1,
                    "fields": fields,
                    "source_url": source_url,
                    "verified": False,
                })

    return records
