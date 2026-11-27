"""Extract published visitation rates from provider text."""

import re

AMOUNT = r"\$\d+(?:\.\d{1,2})?"
RATE = (
    rf"(?:starting\s+at\s+|up\s+to\s+)?"
    rf"{AMOUNT}(?:\s*[-–—]\s*{AMOUNT})?\+?"
)

def extract_hourly_rate(raw_text):
    text = re.sub(r"\s+", " ", raw_text or "").strip()

    labeled = re.search(
        rf"\bhourly(?:\s+(?:rate|fee|visits?))?\s*:\s*({RATE})",
        text,
        re.I,
    )
    if labeled:
        return labeled.group(1) + " / hour"

    pattern = rf"({RATE})\s*(?:/\s*|per\s+)(?:hour|hr)\b"

    for match in re.finditer(pattern, text, re.I):
        before = text[:match.start()]
        after = text[match.end():]

        if re.search(
            r"(?:intake(?:\s+fee)?|exchanges?|orientation|"
            r"additional|court reports?|phone calls?)\s*[:/+-]?\s*$",
            before,
            re.I,
        ):
            continue

        if re.match(
            r"\s*for\s+(?:supervised exchanges?|exchanges?|"
            r"phone calls?|court reports?|per additional child)",
            after,
            re.I,
        ):
            continue

        return match.group(1) + " / hour"

    return None
