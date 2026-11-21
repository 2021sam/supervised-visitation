"""Extract provider candidates from Docling Markdown tables."""

import re


FIELD_NAMES = {
    "location": "location",
    "address": "location",
    "email": "email",
    "phone": "phone",
    "telephone": "phone",
    "website": "website",
    "service area": "service_area",
    "language": "languages",
    "languages": "languages",
    "rate": "rates",
    "rates": "rates",
    "sliding scale": "sliding_scale",
    "provider services": "services",
}


def clean_cell(value):
    return value.strip().replace("&amp;", "&")


def parse_row(line):
    if not line.startswith("|"):
        return None

    cells = [clean_cell(x) for x in line.strip("|").split("|")]

    if len(cells) < 2:
        return None

    if all(re.fullmatch(r"[-:\s]+", x) for x in cells):
        return None

    return cells


def extract_providers(markdown):
    providers = []
    current = None

    def save_current():
        nonlocal current

        if current and current.get("name") and any(
            key in current for key in (
                "phone", "email", "location", "website"
            )
        ):
            providers.append(current)

        current = None

    for line in markdown.splitlines():
        cells = parse_row(line.strip())

        if not cells:
            continue

        label = cells[0].strip().rstrip(":").lower()
        value = " ".join(cells[1:]).strip()

        if label in FIELD_NAMES:
            if current:
                key = FIELD_NAMES[label]
                if value:
                    current[key] = value
            continue

        # Docling provider header rows often repeat the name
        # in both table columns.
        if (
            len(cells) == 2
            and cells[0]
            and cells[0].lower() == cells[1].lower()
        ):
            save_current()
            current = {"name": cells[0]}
            continue

    save_current()
    return providers
