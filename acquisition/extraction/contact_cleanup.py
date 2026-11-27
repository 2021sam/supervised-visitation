"""Shared cleanup of provider contact text.

Preserve original source evidence separately from normalized values.
"""

import re


EMAIL_PATTERN = re.compile(
    r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"
)

PHONE_EXTENSION_PATTERN = re.compile(
    r"\s*(?:ext\.?|extension|x)\s*[:.]?\s*\d+\b",
    re.IGNORECASE,
)


def normalize_fragmented_email(text):
    """Repair whitespace inside otherwise complete email addresses."""
    return re.sub(
        r"([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+)\s+(\.[A-Za-z]{2,})\b",
        r"\1\2",
        text,
    )


def clean_contact_name(name):
    """Remove email addresses and phone extensions from a name."""
    cleaned = normalize_fragmented_email(name)
    cleaned = EMAIL_PATTERN.sub(" ", cleaned)
    cleaned = PHONE_EXTENSION_PATTERN.sub(" ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def clean_embedded_contact_name(name):
    """Remove explicitly labeled contact details from names."""

    cleaned = clean_contact_name(name)

    cleaned = re.split(
        r"\b(?:By Appointment Only|Office|Address|Phone|Email|Website)\s*:",
        cleaned,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]

    cleaned = re.sub(
        r"\(\s*Helpline[^)]*\)",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )

    cleaned = re.sub(
        r"(?:https?://|www\.)[^\s]+",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )

    cleaned = re.sub(r"\s+\.", ".", cleaned)

    return re.sub(r"\s+", " ", cleaned).strip()


PHONE_PATTERN = re.compile(
    r"(?<!\d)(?:\+?1[\s.-]*)?"
    r"(?:\(\s*(\d{3})\s*\)|(\d{3}))"
    r"[\s.-]*(\d{3})[\s.-]*(\d{4})(?!\d)"
)


def normalize_phone_numbers(*values):
    """Extract, normalize and deduplicate published US phone numbers."""
    numbers = []

    for value in values:
        if not value:
            continue

        for match in PHONE_PATTERN.finditer(str(value)):
            area = match.group(1) or match.group(2)
            prefix = match.group(3)
            suffix = match.group(4)

            number = f"({area}) {prefix}-{suffix}"

            if number not in numbers:
                numbers.append(number)

    return "; ".join(numbers)
