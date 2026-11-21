"""Verify official court directories against persisted SQLite providers."""

from pathlib import Path

from acquisition.provider_lead_store import (
    get_saved_provider_identities,
    normalized_provider_identity,
)
from acquisition.extraction.config_loader import load_extraction_config


def verify_official_directory(
    config_path, acquired, database_path, *, state, county
):
    """Verify that a configured, validated directory's providers were saved."""
    config_path = Path(config_path)
    database_path = Path(database_path)

    if not config_path.is_file() or not database_path.is_file():
        return False

    configured_urls = set(load_extraction_config(config_path))
    saved = get_saved_provider_identities(
        root=database_path.parents[2],
        state=state,
        county=county,
    )

    for document in acquired:
        if not document.get("directory_validated"):
            continue

        source_url = (
            document.get("source_url")
            or document.get("candidate_url")
            or document.get("url")
        )

        if source_url not in configured_urls:
            continue

        identities = {
            normalized_provider_identity({
                **record,
                "source_url": source_url,
            })
            for record in document.get("records", [])
        }
        identities.discard(None)

        if identities and identities.issubset(saved):
            return True

    return False
