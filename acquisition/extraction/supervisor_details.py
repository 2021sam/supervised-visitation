"""Orchestrate independent supervisor detail extractors."""

from acquisition.extraction.contact_cleanup import (
    clean_embedded_contact_name,
)
from acquisition.extraction.supervisor_zip import (
    extract_zip_code,
)
from acquisition.extraction.supervisor_service_area import (
    normalize_service_area,
)
from acquisition.extraction.supervisor_languages import (
    extract_languages,
)
from acquisition.extraction.supervisor_additional_info import (
    extract_additional_info,
)


def enrich_supervisor(candidate):
    """Return a supervisor record with enriched published details."""

    return {
        **candidate,
        "name": clean_embedded_contact_name(
            candidate.get("name") or ""
        ),
        "zip_code": extract_zip_code(candidate),
        "service_area": normalize_service_area(
            candidate.get("service_area")
        ),
        "service_counties": normalize_service_area(
            candidate.get("service_counties")
        ),
        "languages": extract_languages(candidate),
        "additional_info": extract_additional_info(candidate),
    }
