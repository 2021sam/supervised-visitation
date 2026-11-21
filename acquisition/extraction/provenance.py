"""Standardize extraction provenance across strategies."""

from datetime import datetime, timezone
from importlib.metadata import (
    PackageNotFoundError,
    version,
)


def extractor_version() -> str:
    """Return the installed engine package version."""
    try:
        return version("supervised-visitation")
    except PackageNotFoundError:
        return "unknown"


def enrich_records(
    records: list[dict],
    *,
    strategy: str,
    source_url: str | None = None,
) -> list[dict]:
    """Add standardized provenance without modifying input records."""

    timestamp = datetime.now(timezone.utc).isoformat()
    engine_version = extractor_version()

    enriched = []

    for record in records:
        result = dict(record)

        result["extraction_method"] = strategy
        result["extraction_version"] = engine_version
        result["extracted_at"] = timestamp

        if source_url is not None:
            result["source_url"] = source_url
        else:
            result.setdefault("source_url", None)

        result["verified"] = False

        enriched.append(result)

    return enriched
