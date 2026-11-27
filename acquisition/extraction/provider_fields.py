"""Parse structured availability and pricing from provider directory text."""

import re

from acquisition.schemas.provider import DAYS


DAY_ALIASES = {
    "mon": "monday",
    "tue": "tuesday",
    "wed": "wednesday",
    "thu": "thursday",
    "fri": "friday",
    "sat": "saturday",
    "sun": "sunday",
}


def parse_time(value):
    """Convert 7am, 7:00am, or 9:00 pm to 24-hour HH:MM."""
    match = re.fullmatch(
        r"\s*(1[0-2]|0?[1-9])(?::([0-5]\d))?\s*(am|pm)\s*",
        value,
        re.I,
    )
    if not match:
        return None

    hour = int(match.group(1)) % 12
    if match.group(3).lower() == "pm":
        hour += 12

    return f"{hour:02d}:{int(match.group(2) or 0):02d}"


def parse_availability(raw):
    """Return explicit days and hours; unknown days remain null."""
    result = {
        "days": {
            day: {"available": None, "hours": []}
            for day in DAYS
        },
        "weekends_available": None,
        "raw_hours_text": raw or None,
    }

    if not raw:
        return result

    text = raw.lower()

    if re.search(r"\b(7|seven)\s+days?\s+a\s+week\b", text):
        selected = list(DAYS)
    else:
        selected = []
        for short, full in DAY_ALIASES.items():
            if re.search(rf"\b{short}[a-z]*\b", text):
                selected.append(full)

    # Each explicitly mentioned day is marked available.
    for day in selected:
        result["days"][day]["available"] = True

    # Match hours like "7:00am to 9:00pm" or "9am to 8pm".
    pattern = (
        r"(\d{1,2}(?::\d{2})?\s*[ap]m)"
        r"\s*(?:to|-|–)\s*"
        r"(\d{1,2}(?::\d{2})?\s*[ap]m)"
    )

    match = re.search(pattern, text)

    if match:
        start = parse_time(match.group(1))
        end = parse_time(match.group(2))

        if start and end:
            # Apply hours only when the schedule clearly covers all days,
            # or when just one specific day is mentioned.
            if len(selected) == 7 or len(selected) == 1:
                for day in selected:
                    result["days"][day]["hours"] = [
                        {"start": start, "end": end}
                    ]

    if (
        result["days"]["saturday"]["available"] is True
        or result["days"]["sunday"]["available"] is True
    ):
        result["weekends_available"] = True

    return result


def parse_pricing(raw):
    """Extract conservative hourly rate ranges and common fees."""
    result = {
        "hourly_rate": {"min": None, "max": None},
        "intake_fee": None,
        "orientation_fee": None,
        "minimum_hours": None,
        "raw_pricing_text": raw or None,
    }

    if not raw:
        return result

    text = raw.lower()

    # Range: $90 to $125 / hour
    range_match = re.search(
        r"\$(\d+(?:\.\d{1,2})?)\s*(?:to|-|–)\s*"
        r"\$(\d+(?:\.\d{1,2})?)\s*/\s*(?:hour|hr)\b",
        text,
    )

    if range_match:
        result["hourly_rate"] = {
            "min": float(range_match.group(1)),
            "max": float(range_match.group(2)),
        }
    else:
        # Single hourly rate: $85 / hour
        hourly_match = re.search(
            r"\$(\d+(?:\.\d{1,2})?)\s*/\s*(?:hour|hr)\b",
            text,
        )

        if hourly_match:
            amount = float(hourly_match.group(1))
            starting_at = bool(
                re.search(
                    r"starting\s+at\s+\$" + re.escape(hourly_match.group(1)),
                    text,
                )
            )
            result["hourly_rate"] = {
                "min": amount,
                "max": None if starting_at else amount,
            }

    intake = re.search(
        r"\$(\d+(?:\.\d{1,2})?)"
        r"\s*(?:one-time\s+)?(?:intake|orientation)\s+fee\b",
        text,
    )

    if not intake:
        intake = re.search(
            r"\$(\d+(?:\.\d{1,2})?)\s+(?:intake|orientation)\b",
            text,
        )

    if intake:
        amount = float(intake.group(1))
        matched_text = intake.group(0).lower()
        if "orientation" in matched_text:
            result["orientation_fee"] = amount
        else:
            result["intake_fee"] = amount

    minimum = re.search(
        r"(\d+(?:\.\d+)?)\s*[- ]?hour\s+minimum\b",
        text,
    )

    if minimum:
        result["minimum_hours"] = float(minimum.group(1))

    return result


def extract_website(text):
    """Extract a published website without guessing a URL."""
    if not text:
        return None

    # Remove email addresses so their domains aren't mistaken for websites.
    cleaned = re.sub(
        r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}",
        " ",
        text,
    )

    match = re.search(
        r"(?<![\w@])"
        r"((?:https?://)?(?:www\.)?"
        r"[a-zA-Z0-9][a-zA-Z0-9-]*"
        r"(?:\.[a-zA-Z0-9-]+)*"
        r"\.[a-zA-Z]{2,}"
        r"(?:/[^\s|<>]*)?)",
        cleaned,
        re.I,
    )

    if not match:
        return None

    url = match.group(1).rstrip(".,;)")
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    return url


def normalize_website(value):
    """Normalize a published website without inventing missing URLs."""

    if not value:
        return ""

    value = str(value).strip()

    if value.casefold() in {
        "", "none", "n/a", "na", "null",
        "not available", "no website", "no",
    }:
        return ""

    # Repair Markdown escapes and fragmented URL punctuation.
    value = value.replace(r"\_", "_")
    value = re.sub(r"\s*-\s*", "-", value)
    value = re.sub(r"\s*\.\s*", ".", value)

    return extract_website(value) or ""
