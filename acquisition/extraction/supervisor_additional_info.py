"""Preserve additional published supervisor information."""

import re
from html import unescape


def extract_additional_info(candidate):
    """Combine explicitly extracted informational fields."""

    sections = []
    seen = set()

    fields = (
        ("additional_info", ""),
        ("intake_fee", "Intake fee"),
        ("rates", "Published rates"),
        ("availability", "Availability"),
        ("services", "Services"),
        ("trustline", "TrustLine"),
        ("trustline_id", "TrustLine"),
    )

    for field, label in fields:
        value = candidate.get(field)

        if not value:
            continue

        text = unescape(str(value))
        text = re.sub(r"\s+", " ", text).strip()

        if not text or text.casefold() in seen:
            continue

        seen.add(text.casefold())

        if label:
            sections.append(f"{label}: {text}")
        else:
            sections.append(text)

    return "\n".join(sections)
