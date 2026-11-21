"""Acquire discovered and explicitly configured court documents."""

from pathlib import Path
from urllib.parse import urlsplit

from .config_loader import load_extraction_config
from ..pipeline import acquire_candidates


def acquire_county_candidates(
    candidates,
    *,
    config_path: str | Path,
    fetch,
    allowed_host: str | None,
    progress_callback=None,
    include_discovered=False,
):
    """Acquire configured court documents, discovered or explicitly listed."""
    config_path = Path(config_path)

    if not config_path.is_file():
        return []

    configurations = load_extraction_config(config_path)

    # Preserve discovered candidate metadata where available.
    candidates_by_url = {
        candidate["url"]: candidate
        for candidate in candidates
        if include_discovered or candidate["url"] in configurations
    }

    # Include explicitly configured documents not found by the crawler.
    for url in configurations:
        if allowed_host is not None and urlsplit(url).hostname != allowed_host:
            raise ValueError(
                f"Configured document outside authorized court host: {url}"
            )

        candidates_by_url.setdefault(
            url,
            {
                "url": url,
                "method": "configured",
                "verified": False,
            },
        )

    return acquire_candidates(
        list(candidates_by_url.values()),
        fetch=fetch,
        config_by_url=configurations,
        allowed_host=allowed_host,
        progress_callback=progress_callback,
    )
