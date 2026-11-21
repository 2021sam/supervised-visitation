"""Extract supervised visitation provider candidates from saved HTML."""

import re
from pathlib import Path

from bs4 import BeautifulSoup


PHONE_RE = re.compile(
    r"(?:\+1[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}"
)

EMAIL_RE = re.compile(
    r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}"
)

NEGATIVE = (
    "family court services",
    "supervised visitation providers",
    "legal requirements",
    "provider information",
    "additional information",
    "contact information",
)


def clean(value):
    return re.sub(r"\s+", " ", value or "").strip()


def clean_provider_name(value):
    """Remove contact details appended to provider names."""
    value = clean(value)

    # Contact labels, phone numbers, emails, and street addresses.
    patterns = [
        r"\b(?:Contact|Phone|Email|Website|Web)\s*:",
        PHONE_RE.pattern,
        EMAIL_RE.pattern,
        r"\s+\d{1,6}\s+(?=[A-Za-z])",
    ]

    positions = []

    for pattern in patterns:
        match = re.search(pattern, value, flags=re.IGNORECASE)
        if match:
            positions.append(match.start())

    if positions:
        value = value[:min(positions)]

    return clean(value).strip(" ,;-")

def candidate(name, text, source):
    name = clean_provider_name(name)
    text = clean(text)

    if not 3 <= len(name) <= 120:
        return None

    if name.lower() in NEGATIVE:
        return None

    phones = list(dict.fromkeys(PHONE_RE.findall(text)))
    emails = list(dict.fromkeys(EMAIL_RE.findall(text)))

    if not phones and not emails:
        return None

    return {
        "name": name,
        "phones": phones,
        "emails": emails,
        "raw_text": text,
        "source_element": source,
    }


def extract_html_providers(path):
    """Return provider candidates with their original source text."""
    soup = BeautifulSoup(
        Path(path).read_text(encoding="utf-8", errors="replace"),
        "html.parser",
    )

    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()

    results = []
    seen = set()

    def add(record):
        if not record:
            return

        key = (
            record["name"].casefold(),
            tuple(record["phones"]),
            tuple(record["emails"]),
        )

        if key not in seen:
            seen.add(key)
            results.append(record)

    # Pattern 1: Paragraph with bold provider name.
    for p in soup.find_all("p"):
        strong = p.find(["strong", "b"], recursive=False)

        if not strong:
            continue

        name = strong.get_text(" ", strip=True)
        text = p.get_text(" ", strip=True)

        add(candidate(name, text, "paragraph"))

    # Pattern 2: Table rows with contact information.
    for table in soup.find_all("table"):
        for tr in table.find_all("tr"):
            cells = tr.find_all(["td", "th"], recursive=False)

            if len(cells) < 2:
                continue

            name = cells[0].get_text(" ", strip=True)
            text = tr.get_text(" ", strip=True)

            add(candidate(name, text, "table"))

    # Pattern 3: Repeated list or content blocks.
    for tag in soup.find_all(["li", "article"]):
        text = tag.get_text(" ", strip=True)

        if not 20 <= len(text) <= 1500:
            continue

        heading = tag.find(["strong", "b", "h3", "h4"])

        if not heading:
            continue

        name = heading.get_text(" ", strip=True)

        add(candidate(name, text, "block"))

    return results
