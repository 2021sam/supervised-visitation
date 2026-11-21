"""Extract provider records from row-oriented and column-oriented PDF tables."""

import re

import pymupdf


PHONE = re.compile(
    r"(?<!\d)(?:\+1[\s.-]?)?"
    r"\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}(?!\d)"
)
EMAIL = re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")


def clean(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def contact_fields(value):
    text = clean(value)
    phone = PHONE.search(text)
    email = EMAIL.search(text)

    return {
        "phone": phone.group(0) if phone else "",
        "email": email.group(0) if email else "",
    }


def extract_row_table(rows, page_number, source_url):
    """Providers are rows beneath Provider / Phone headers."""
    records = []

    header_index = None
    for index, row in enumerate(rows):
        cells = [clean(cell).casefold() for cell in row]
        if (
            len(cells) >= 2
            and cells[0] == "provider"
            and ("phone" in cells[1] or "email" in cells[1])
        ):
            header_index = index
            break

    if header_index is None:
        # Continued provider tables may omit their column headings.
        # Require a six-column layout with multiple contactable rows.
        if not rows or not all(len(row) == 6 for row in rows):
            return records

        contactable = sum(
            bool(contact_fields(row[1])["phone"] or
                 contact_fields(row[1])["email"])
            for row in rows
        )

        if contactable < 2:
            return records

        header_index = -1

    for row in rows[header_index + 1:]:
        if len(row) < 2:
            continue

        name = clean(row[0])
        contacts = contact_fields(row[1])

        if not name or not any(contacts.values()):
            continue

        records.append({
            "page": page_number,
            "source_url": source_url,
            "verified": False,
            "fields": {
                "name": name,
                **contacts,
            },
        })

    return records


def extract_column_table(rows, page_number, source_url):
    """Providers are columns with Agency, Phone and contact rows."""
    if not rows:
        return []

    agency_row = next(
        (
            row for row in rows
            if row and clean(row[0]).casefold() == "agency"
        ),
        None,
    )

    phone_row = next(
        (
            row for row in rows
            if row and clean(row[0]).casefold() == "phone"
        ),
        None,
    )

    contact_row = next(
        (
            row for row in rows
            if row and "email" in clean(row[0]).casefold()
        ),
        None,
    )

    if agency_row is None or phone_row is None:
        return []

    records = []
    for column in range(1, len(agency_row)):
        name = clean(agency_row[column])

        if not name:
            continue

        phone_text = (
            phone_row[column] if column < len(phone_row) else ""
        )
        contact_text = (
            contact_row[column]
            if contact_row is not None and column < len(contact_row)
            else ""
        )

        contacts = contact_fields(
            f"{clean(phone_text)} {clean(contact_text)}"
        )

        if not any(contacts.values()):
            continue

        records.append({
            "page": page_number,
            "source_url": source_url,
            "verified": False,
            "fields": {
                "name": name,
                **contacts,
            },
        })

    return records


def extract_pdf_provider_tables(
    pdf_bytes, *, start_page=0, source_url=None
):
    """Automatically detect row- or column-oriented provider tables."""
    records = []

    with pymupdf.open(stream=pdf_bytes, filetype="pdf") as pdf:
        for page_index in range(start_page, len(pdf)):
            page = pdf[page_index]

            for table in page.find_tables().tables:
                rows = table.extract()

                records.extend(
                    extract_row_table(
                        rows, page_index + 1, source_url
                    )
                )
                records.extend(
                    extract_column_table(
                        rows, page_index + 1, source_url
                    )
                )

    return records
