"""Extract explicitly published supervisor languages."""

import re
from html import unescape


LANGUAGES = (
    "English", "Spanish", "Mandarin", "Cantonese",
    "Chinese", "Vietnamese", "Tagalog", "Filipino",
    "Korean", "Japanese", "Hindi", "Punjabi",
    "Urdu", "Arabic", "Farsi", "Persian",
    "Armenian", "Russian", "Ukrainian", "French",
    "Portuguese", "German", "Italian", "Thai",
    "Samoan", "Hmong", "Khmer", "Lao",
    "Hebrew", "Turkish", "Bengali", "Gujarati",
    "American Sign Language", "ASL", "Somali",
)

LANGUAGE_PATTERN = re.compile(
    r"\b(?:" + "|".join(
        re.escape(language)
        for language in sorted(LANGUAGES, key=len, reverse=True)
    ) + r")\b",
    re.IGNORECASE,
)

CANONICAL = {
    language.casefold(): language
    for language in LANGUAGES
}


def extract_languages(candidate):
    """Return explicitly declared languages in published order."""

    structured = candidate.get("languages") or ""

    if isinstance(structured, (list, tuple)):
        structured = ", ".join(map(str, structured))

    if structured:
        return unescape(str(structured)).strip()

    text = unescape(str(candidate.get("additional_info") or ""))
    languages = []

    for segment in re.split(r"[•;\n]+", text):
        segment = segment.strip()

        if re.search(r"\breferrals?\b", segment, re.I):
            continue

        cleaned = re.sub(
            r"^(?:languages?(?: spoken)?|multilingual|bilingual)"
            r"\s*[:\-]?\s*",
            "",
            segment,
            flags=re.I,
        ).strip(" ()")

        matches = LANGUAGE_PATTERN.findall(cleaned)

        if not matches:
            continue

        remainder = LANGUAGE_PATTERN.sub("", cleaned)
        remainder = re.sub(r"\band\b", "", remainder, flags=re.I)

        if remainder.strip(" ,&/()."):
            continue

        for match in matches:
            language = CANONICAL[match.casefold()]

            if language not in languages:
                languages.append(language)

    return ", ".join(languages)
