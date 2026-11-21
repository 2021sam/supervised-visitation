"""Extract providers from heading-based Markdown directories."""

import html
import re

from acquisition.extraction.provider_fields import extract_website


PHONE_PATTERN = re.compile(
    r"(?:\+?1[\s.-]?)?"
    r"(?:\(\d{3}\)|\d{3})[\s.-]?"
    r"\d{3}[\s.-]?\d{4}"
)

EMAIL_PATTERN = re.compile(
    r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}"
)

EXCLUDED_HEADINGS = (
    "for referrals",
    "revised ",
    "this list",
    "disclaimer",
    "monterey county supervised visitation providers",
    "resource list for supervised visitation providers",
    "providers information",
    "nota:",
    "tenga en cuenta:",
    "please note",
    "important notice",
    "supervised visitation providers please note",
)


def clean_text(value):
    value = html.unescape(value)
    value = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", value)
    return re.sub(r"\s+", " ", value).strip()


def extract_heading_providers(markdown):
    """Extract candidate records from heading-led provider blocks."""

    providers = []
    heading = None
    body = []

    def flush():
        if not heading:
            return

        name = clean_text(heading).lstrip("* ").strip()

        if not name or any(
            name.lower().startswith(prefix)
            for prefix in EXCLUDED_HEADINGS
        ):
            return

        # Document dates are not provider names.
        if re.fullmatch(
            r"(?:January|February|March|April|May|June|July|"
            r"August|September|October|November|December)"
            r"\s+\d{4}",
            name,
            re.IGNORECASE,
        ):
            return

        raw = "\n".join(body).strip()
        if not raw:
            return

        cleaned = clean_text(raw)
        phones = list(dict.fromkeys(PHONE_PATTERN.findall(cleaned)))
        emails = list(dict.fromkeys(EMAIL_PATTERN.findall(cleaned)))

        # Require contact evidence to reduce false positives.
        if not phones and not emails:
            return

        record = {
            "name": name,
            "raw_text": heading + "\n" + raw,
        }

        if phones:
            record["phone"] = phones[0]

        if emails:
            record["email"] = emails[0]

        website = extract_website(cleaned)
        if website:
            record["website"] = website

        providers.append(record)

    for line in markdown.splitlines():
        match = re.match(r"^#{2,3}\s+(.+?)\s*$", line)

        if match:
            flush()
            heading = match.group(1)
            body = []
        elif heading is not None:
            body.append(line)

    flush()
    return providers
