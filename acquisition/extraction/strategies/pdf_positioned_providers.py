"""Extract provider records from PDFs with positioned text columns."""

import re

import pymupdf


PHONE = re.compile(
    r"(?<!\d)(?:\+1[\s.-]?)?"
    r"\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}(?!\d)"
)
EMAIL = re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")
ADDRESS = re.compile(
    r"^\d+\s+\S+|"
    r"\b(?:CA|California)\s+\d{5}(?:-\d{4})?\b",
    re.IGNORECASE,
)


def page_lines(page):
    """Return positioned text lines in reading order."""
    result = []

    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            text = " ".join(
                span["text"] for span in line["spans"]
            ).strip()

            if text:
                x0, y0, _, _ = line["bbox"]
                result.append((y0, x0, text))

    return sorted(result)


def extract_pdf_positioned_providers(
    pdf_bytes, *, start_page=0, source_url=None
):
    """Extract contact groups from positioned PDF text."""
    records = []

    with pymupdf.open(stream=pdf_bytes, filetype="pdf") as pdf:
        for page_index in range(start_page, len(pdf)):
            page = pdf[page_index]
            lines = page_lines(page)

            headers = [
                (x, y)
                for y, x, text in lines
                if "name and contact information" in text.casefold()
            ]

            if not headers:
                continue

            header_x, header_y = headers[0]

            email_headers = [
                x
                for y, x, text in lines
                if abs(y - header_y) < 12
                and text.strip().casefold() == "email"
            ]

            if not email_headers:
                continue

            right = (header_x + min(email_headers)) / 2
            left = max(0, header_x - 30)

            contacts = [
                (y, text)
                for y, x, text in lines
                if y > header_y and left <= x < right
            ]

            if not contacts:
                continue

            # Use the first row of each provider's service
            # information as a provider-block boundary.
            service_x = [
                x
                for y, x, text in lines
                if abs(y - header_y) < 12
                and "services offered" in text.casefold()
            ]

            if not service_x:
                continue

            service_left = min(service_x) - 20

            service_lines = [
                (y, text)
                for y, x, text in lines
                if y > header_y
                and service_left <= x < service_left + 100
                and "supervised exchange" in text.casefold()
            ]

            starts = sorted({y for y, _ in service_lines})

            if not starts:
                continue

            for index, start_y in enumerate(starts):
                end_y = (
                    starts[index + 1]
                    if index + 1 < len(starts)
                    else page.rect.height
                )

                section = [
                    (y, text)
                    for y, text in contacts
                    if start_y - 1 <= y < end_y - 1
                ]

                phones = []
                names = []

                for _, text in section:
                    found = PHONE.findall(text)

                    if found:
                        phones.extend(found)
                    elif not ADDRESS.search(text):
                        names.append(text)

                if not phones or not names:
                    continue

                email = ""

                for y, x, text in lines:
                    if start_y - 1 <= y < end_y - 1 and x >= right:
                        match = EMAIL.search(text)
                        if match:
                            email = match.group(0)
                            break

                records.append({
                    "page": page_index + 1,
                    "source_url": source_url,
                    "verified": False,
                    "fields": {
                        "name": names[-1],
                        "contact_person": names[0],
                        "phone": phones[0],
                        "phones": phones,
                        "email": email,
                    },
                })

    return records
