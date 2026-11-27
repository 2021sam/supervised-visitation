"""Extract explicitly published US ZIP codes."""

import re


STATE_CODES = (
    "AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY "
    "LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH "
    "OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY"
).split()

ZIP_PATTERN = re.compile(
    r"\b(?:" + "|".join(STATE_CODES) + r"|California)"
    r"\s+([0-9]{5})(?:-[0-9]{4})?\b",
    re.IGNORECASE,
)


def extract_zip_code(candidate):
    """Return the first explicitly published ZIP code."""

    published = str(candidate.get("zip_code") or "").strip()

    if re.fullmatch(r"[0-9]{5}(?:-[0-9]{4})?", published):
        return published[:5]

    for field in ("location", "name", "raw_text"):
        text = str(candidate.get(field) or "")
        match = ZIP_PATTERN.search(text)

        if match:
            return match.group(1)

    return ""
