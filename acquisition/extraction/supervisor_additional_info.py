"""Preserve additional published supervisor information."""

import re
from html import unescape
from acquisition.extraction.supervisor_hourly_rate import extract_hourly_rate


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

        if (
            field == "rates"
            and candidate.get("hourly_rate_labeled")
            and not re.search(r"\b(?:hour|hr)\b", text, re.I)
        ):
            text += " / hour"

        seen.add(text.casefold())

        if label:
            sections.append(f"{label}: {text}")
        else:
            sections.append(text)

    if not candidate.get("rates"):
        rate = extract_hourly_rate(candidate.get("raw_text"))
        if rate:
            sections.append(f"Published rates: {rate}")

    return "\n".join(sections)
