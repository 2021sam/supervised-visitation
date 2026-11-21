"""Classify discovered source candidates without fetching their contents."""

import re
from urllib.parse import unquote, urlparse


DOCUMENT_RULES = (
    (
        "declaration_form",
        r"\b(?:fl[\s-]*324\w*|declaration)\b",
    ),
    (
        "application_form",
        r"\b(?:application|screening|registration)\b",
    ),
    (
        "instructional_guide",
        r"\b(?:guide|handbook|instructions?|manual)\b",
    ),
)

DIRECTORY_PATTERN = re.compile(
    r"\b(?:provider|monitor|referral|resource)"
    r"[\s-]*(?:list|directory)\b"
    r"|\b(?:list|directory)[\s-]*of[\s-]*"
    r"(?:providers?|monitors?)\b"
    r"|\bsupervised[\s-]*(?:visitation|visit|exchange)"
    r"[\s-]*(?:providers?[\s-]*)?(?:list|directory)\b",
    re.I,
)


def classify_candidate(candidate):
    """Return a provisional classification with supporting evidence.

    This function does not download, parse, or verify the source.
    """
    url = candidate.get("url", "")
    label = candidate.get("text", "")
    source_type = candidate.get("source_type", "unknown")

    path = unquote(urlparse(url).path)
    haystack = (
        path.replace("_", " ").replace("-", " ")
        + " "
        + label.replace("_", " ").replace("-", " ")
    ).lower()

    if source_type == "html_directory":
        return {
            "classification": "possible_html_directory",
            "verified": False,
            "reason": "HTML structure detected; provider records unverified",
        }

    for category, pattern in DOCUMENT_RULES:
        if re.search(pattern, haystack, re.I):
            return {
                "classification": category,
                "verified": False,
                "reason": "Matched document title or URL pattern",
            }

    if DIRECTORY_PATTERN.search(haystack):
        return {
            "classification": "provider_directory_candidate",
            "verified": False,
            "reason": "Directory terminology in title or URL",
        }

    if source_type == "html_directory":
        return {
            "classification": "possible_html_directory",
            "verified": False,
            "reason": "HTML structure detected; provider records unverified",
        }

    return {
        "classification": "needs_review",
        "verified": False,
        "reason": "Insufficient evidence for classification",
    }
