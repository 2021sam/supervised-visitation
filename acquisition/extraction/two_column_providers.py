"""Extract providers from two-column supervised-visitation tables."""

import re

from acquisition.extraction.markdown_providers import parse_row
from acquisition.extraction.provider_fields import extract_website


PHONE = re.compile(
    r"(?<![\w])"
    r"(?:\+?1[\s.-]?)?"
    r"(?:\(\d{3}\)|\d{3})[\s.-]?"
    r"\d{3}[\s.-]?\d{4}"
    r"(?!\d)"
)

EMAIL = re.compile(
    r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}"
)

HEADING = re.compile(
    r"^supervised visitation providers$",
    re.IGNORECASE,
)


def extract_two_column_providers(markdown):
    """Extract one provider per cell from recognized two-column tables."""

    providers = []
    active = False

    for line in markdown.splitlines():
        stripped = line.strip()

        if not stripped:
            continue

        if not stripped.startswith("|"):
            if active:
                active = False
            continue

        cells = parse_row(stripped)

        # Markdown separator rows are not table boundaries.
        if re.fullmatch(r"[|:\-\s]+", stripped):
            continue

        if not cells or len(cells) != 2:
            active = False
            continue

        if all(HEADING.fullmatch(cell.strip()) for cell in cells):
            active = True
            continue

        if not active:
            continue

        if all(
            re.fullmatch(r":?-{3,}:?", cell.strip())
            for cell in cells
        ):
            continue

        for cell in cells:
            cell = cell.strip()

            if not cell:
                continue

            phones = PHONE.findall(cell)
            emails = EMAIL.findall(cell)

            if not phones and not emails:
                continue

            positions = [
                match.start()
                for pattern in (PHONE, EMAIL)
                for match in pattern.finditer(cell)
            ]

            name = cell[:min(positions)].strip()

            if not name:
                continue

            providers.append({
                "name": name,
                "phone": phones[0] if phones else "",
                "email": emails[0] if emails else "",
                "website": extract_website(cell) or "",
                "raw_text": cell,
            })

    return providers
