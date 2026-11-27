"""Normalize published supervisor service areas."""

import re
from html import unescape


def normalize_service_area(value):
    """Preserve published service areas in their original order."""

    if not value:
        return ""

    text = unescape(str(value))
    parts = re.split(r"[•;,\n]+", text)

    areas = []
    seen = set()

    for part in parts:
        area = re.sub(r"\s+", " ", part).strip()
        key = area.casefold()

        if area and key not in seen:
            areas.append(area)
            seen.add(key)

    return ", ".join(areas)
