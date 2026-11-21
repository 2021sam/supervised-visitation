"""Automatically acquire discovered county court documents.

Uses the existing configured extraction pipeline when a configuration
exists, and the existing automatic strategies otherwise.
"""

from pathlib import Path

from .extraction.county_acquisition import acquire_county_candidates
from .pipeline import acquire_candidates


def acquire_county_documents(
    candidates,
    *,
    config_path,
    fetch,
    allowed_host,
    progress_callback=None,
    include_discovered=False,
):
    """Acquire discovered candidates using the existing extraction engine."""
    config_path = Path(config_path)

    if config_path.is_file():
        return acquire_county_candidates(
            candidates,
            config_path=config_path,
            fetch=fetch,
            allowed_host=allowed_host,
            progress_callback=progress_callback,
            include_discovered=include_discovered,
        )

    return acquire_candidates(
        candidates,
        fetch=fetch,
        allowed_host=allowed_host,
        progress_callback=progress_callback,
    )
