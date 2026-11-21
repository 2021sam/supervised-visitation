"""Extract provider records from label-value PDF directories."""

import re


FIELD_MAP = {
    "name of provider": "name",
    "email": "email",
    "phone": "phone",
    "website": "website",
    "address": "location",
    "area served": "service_area",
    "hourly rate": "rates",
    "sliding scale": "sliding_scale",
    "intake & report fees": "intake_report_fees",
    "intake &amp; report fees": "intake_report_fees",
    "additional child fee": "additional_child_fee",
    "location of visits": "visit_location",
    "length of visits": "visit_duration",
    "hours of operation": "availability",
    "languages": "languages",
    "exchanges": "exchanges",
}


def clean_value(value):
    value = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", value)
    return re.sub(r"\s+", " ", value).strip()


def extract_label_value_providers(markdown):
    """Parse repeated Name of Provider blocks into candidates."""
    providers = []
    current = None

    for line in markdown.splitlines():
        line = line.strip()

        if not line:
            continue

        match = re.match(
            r"^(?:[-*]\s*)?([^:]{2,50}):\s*(.*)$",
            line,
            re.I,
        )

        if not match:
            continue

        label = re.sub(r"\s+", " ", match.group(1)).strip().lower()
        value = clean_value(match.group(2))

        key = FIELD_MAP.get(label)

        if key == "name":
            if current and current.get("name"):
                providers.append(current)

            current = {"name": value, "raw_lines": [line]}
            continue

        if current is None:
            continue

        current["raw_lines"].append(line)

        if key and value:
            current[key] = value
            if label == "hourly rate":
                current["hourly_rate_labeled"] = True

    if current and current.get("name"):
        providers.append(current)

    for provider in providers:
        provider["raw_text"] = "\n".join(
            provider.pop("raw_lines")
        )

    return providers
