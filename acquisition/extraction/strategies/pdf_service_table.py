"""Extract supervised-visitation listings from PDF service-category tables."""

import re

import pymupdf


PHONE = re.compile(
    r"(?<!\d)(?:\(?\d{3}\)?[\s.-]*)\d{3}[\s.-]*\d{4}(?!\d)"
)

HEADING = re.compile(
    r"\bsupervised\s+visitation\b",
    re.IGNORECASE,
)

WEBSITE = re.compile(
    r"^(?:https?://)?(?:www\.)?"
    r"[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+"
    r"(?:/[^\s]*)?$",
    re.IGNORECASE,
)


def _split_cell(value):
    """Split provider entries, retaining websites after phone numbers."""

    lines = [
        line.strip()
        for line in value.splitlines()
        if line.strip()
    ]

    records = []
    current = []

    for line in lines:
        if WEBSITE.fullmatch(line):
            if records and not current:
                records[-1].append(line)
            elif current:
                current.append(line)
            continue

        current.append(line)

        if PHONE.search(line):
            records.append(current)
            current = []

    return records



def extract_pdf_service_table(
    pdf_bytes,
    *,
    start_page=0,
    source_url=None,
):
    """Find supervised-visitation columns and extract provider candidates."""

    records = []

    with pymupdf.open(stream=pdf_bytes, filetype="pdf") as pdf:
        for page_index in range(start_page, len(pdf)):
            page = pdf[page_index]

            for table in page.find_tables().tables:
                rows = table.extract()

                supervised_columns = set()

                for row in rows:
                    for index, value in enumerate(row):
                        if value and HEADING.search(value):
                            supervised_columns.add(index)

                if len(supervised_columns) != 1:
                    continue

                column = supervised_columns.pop()

                for row in rows:
                    if column >= len(row):
                        continue

                    value = row[column]

                    if not value or HEADING.search(value):
                        continue

                    for group in _split_cell(value):
                        phone_index = next(
                            (
                                index
                                for index, line in enumerate(group)
                                if PHONE.search(line)
                            ),
                            None,
                        )

                        if phone_index is None or phone_index < 2:
                            continue

                        phone = PHONE.search(
                            group[phone_index]
                        ).group()

                        name_lines = group[:phone_index - 1]
                        city = group[phone_index - 1]

                        if not name_lines:
                            continue

                        website = next(
                            (
                                line
                                for line in group[phone_index + 1:]
                                if WEBSITE.fullmatch(line)
                            ),
                            None,
                        )

                        records.append({
                            "page": page_index + 1,
                            "fields": {
                                "name": " ".join(name_lines),
                                "city": city,
                                "phone": phone,
                                "website": website,
                                "service": "Supervised Visitation",
                                "raw_lines": group,
                            },
                            "source_url": source_url,
                            "verified": False,
                        })

    return records
