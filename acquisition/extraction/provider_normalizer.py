"""Convert extracted provider candidates to canonical JSON records."""

import re

from acquisition.schemas.provider import new_provider
from acquisition.extraction.provider_fields import extract_website, parse_availability, parse_pricing


def normalize_provider(candidate, source=None):
    """Normalize a provider candidate without inventing missing data."""

    record = new_provider()
    source = source or {}

    record["name"] = (
        candidate.get("contact_person")
        or candidate.get("provider_name")
        or candidate.get("name")
    )
    record["business_name"] = candidate.get("business_name")

    record["contact"]["phones"] = list(dict.fromkeys(
        candidate.get("phones", [])
        or ([candidate["phone"]] if candidate.get("phone") else [])
    ))

    record["contact"]["emails"] = list(dict.fromkeys(
        candidate.get("emails", [])
        or ([candidate["email"]] if candidate.get("email") else [])
    ))

    record["contact"]["website"] = (
        extract_website(candidate.get("website"))
        or extract_website(candidate.get("raw_text"))
    )

    record["location"]["state"] = source.get("state")
    record["location"]["country"] = "US"

    location = candidate.get("location")
    if location:
        record["location"]["raw_address"] = location

    service_area = candidate.get("service_area")
    if service_area:
        record["service_areas"]["raw_text"] = service_area

    languages = candidate.get("languages")
    if languages:
        record["languages"] = [
            language.strip()
            for language in re.split(r",|;|\band\b", languages)
            if language.strip()
        ]

    rates = candidate.get("rates")
    if rates:
        record["pricing"]["raw_pricing_text"] = rates

    sliding = candidate.get("sliding_scale")
    if sliding:
        value = sliding.strip().lower()
        if value in ("yes", "true"):
            record["pricing"]["sliding_scale_available"] = True
        elif value in ("no", "false"):
            record["pricing"]["sliding_scale_available"] = False

    services = candidate.get("services")
    if services:
        record["services"]["other_services"] = [services]

    if candidate.get("availability"):
        record["availability"].update(
            parse_availability(candidate["availability"])
        )

    if candidate.get("rates"):
        rate_text = candidate["rates"].strip()

        # Label-value directories identify this field as "Hourly Rate".
        # Preserve that context when the value contains only a dollar amount.
        if (
            candidate.get("hourly_rate_labeled")
            and not __import__("re").search(
                r"\b(?:hour|hr)\b|/\s*(?:hour|hr)\b",
                rate_text,
                __import__("re").I,
            )
        ):
            rate_text += " / hour"

        record["pricing"].update(
            parse_pricing(rate_text)
        )
        record["pricing"]["raw_pricing_text"] = candidate["rates"]

    source_type = source.get("type", "court_pdf")

    record["source"].update({
        "type": source_type,
        "state": source.get("state"),
        "county": source.get("county") or candidate.get("county"),
        "url": source.get("url") or candidate.get("source_url"),
        "local_file": source.get("local_file") or candidate.get("source_file"),
        "extraction_engine": (
            "beautifulsoup" if source_type == "court_html" else "docling"
        ),
        "extracted_at": source.get("extracted_at"),
        "raw_provider_text": candidate.get("raw_text"),
    })

    if source_type == "court_html":
        record["metadata"]["review_required"] = True

    return record
