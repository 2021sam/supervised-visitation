"""Connect discovered document candidates to extraction and validation."""

from urllib.parse import urlparse

from .core import safe_public_url
from .extraction.orchestrator import extract_document
from .extraction.directory_validator import validate_provider_directory


def acquire_candidates(
    candidates,
    *,
    fetch,
    config_by_url=None,
    allowed_host=None,
    progress_callback=None,
):
    """Retrieve, classify, extract, and validate candidate documents.

    fetch(url) must return (effective_url, content_type, content_bytes).
    Extracted provider records remain independently unverified.
    """
    config_by_url = config_by_url or {}
    results = []
    downloads_attempted = 0
    downloads_succeeded = 0
    downloads_failed = 0

    for candidate in candidates:
        url = candidate["url"]

        try:
            safe_public_url(url)

            if allowed_host is not None:
                if urlparse(url).hostname.lower() != allowed_host.lower():
                    raise ValueError("Candidate left allowed host")

            downloads_attempted += 1

            if progress_callback is not None:
                progress_callback(
                    9,
                    current_document=url,
                    documents_total=len(candidates),
                    downloads_attempted=downloads_attempted,
                )

            effective_url, content_type, content = fetch(url)
            safe_public_url(effective_url)

            if allowed_host is not None:
                if (
                    urlparse(effective_url).hostname.lower()
                    != allowed_host.lower()
                ):
                    raise ValueError("Redirect left allowed host")

            if not isinstance(content, bytes):
                raise ValueError("Fetcher must return bytes")

            downloads_succeeded += 1

            if progress_callback is not None:
                progress_callback(
                    9,
                    current_document=url,
                    downloads_attempted=downloads_attempted,
                    downloads_succeeded=downloads_succeeded,
                    downloads_failed=downloads_failed,
                    status="completed",
                )

            normalized_type = content_type.split(";")[0].strip().lower()
            document_type = "unknown"

            if progress_callback is not None:
                progress_callback(
                    10,
                    current_document=url,
                    operation="extracting_document",
                )

            result = extract_document(
                content,
                content_type=content_type,
                source_url=effective_url,
                config=config_by_url.get(url, {}),
            )

            source_description = candidate.get("text", "")

            if progress_callback is not None:
                progress_callback(
                    11,
                    current_document=url,
                    records_to_validate=len(result.records),
                    operation="validating_directory",
                )

            validation = validate_provider_directory(
                result.records,
                source_description=source_description,
            )

            if validation.is_directory:
                document_type = "directory"

            results.append({
                "candidate_url": url,
                "source_url": effective_url,
                "status": result.status,
                "strategy": result.strategy,
                "records": result.records,
                "reason": result.reason,
                "document_type": document_type,
                "directory_validated": validation.is_directory,
                "validation_reason": validation.reason,
            })

        except (ValueError, RuntimeError, OSError) as exc:
            if downloads_attempted > downloads_succeeded + downloads_failed:
                downloads_failed += 1
                if progress_callback is not None:
                    progress_callback(
                        9,
                        current_document=url,
                        downloads_attempted=downloads_attempted,
                        downloads_succeeded=downloads_succeeded,
                        downloads_failed=downloads_failed,
                        status="failed",
                    )

            results.append({
                "candidate_url": url,
                "source_url": None,
                "status": "acquisition_failed",
                "strategy": None,
                "records": [],
                "reason": str(exc),
                "document_type": "unknown",
                "directory_validated": False,
                "validation_reason": "",
            })

    return results
