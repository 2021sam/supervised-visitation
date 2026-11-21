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
