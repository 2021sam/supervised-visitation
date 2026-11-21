"""Resolve county provider-list status from verified extraction evidence."""


def resolve_provider_status(
    crawl_status,
    *,
    previous_status=None,
    saved_lead_count=0,
    candidates_found=0,
    validated_found=0,
    directory_found=False,
    search_incomplete=False,
    official_directory_verified=False,
):
    """Require validated directory evidence and saved provider records.

    A discovered URL, candidate document, or directory_found flag
    alone does not establish FOUND.
    """

    # Manual MIA classification is terminal until explicitly reset.
    if previous_status == "mia":
        return "mia"

    if (
        official_directory_verified
        and validated_found > 0
        and saved_lead_count > 0
    ):
        return "found"

    # A later crawl cannot downgrade a previously confirmed directory.
    # New FOUND classifications still require validated, saved records.
    if previous_status == "found":
        return "found"

    if previous_status == "mia":
        return "mia"

    if candidates_found or validated_found or directory_found:
        return "unconfirmed"

    if previous_status == "pending_manual_review":
        return "pending_manual_review"

    if search_incomplete:
        return "incomplete"

    if crawl_status == "completed":
        return "not_found"

    if crawl_status == "access_failed":
        return "access_failed"

    return "incomplete"


def classify_saved_county_status(evidence, saved, saved_lead_count):
    """Report persisted county status without losing completed acquisitions."""
    status = evidence.get("provider_list_status")

    # Manual MIA classifications remain terminal.
    if status == "mia":
        return "mia"

    has_records = saved_lead_count > 0
    validated = (
        int(evidence.get("validated_directory_count") or 0) > 0
        or bool(saved.get("validated"))
    )
    official_verified = bool(evidence.get("official_directory_verified"))

    # Honor completed acquisitions with persisted provider records.
    if has_records and (
        status == "found"
        or (validated and (
            official_verified or status == "access_failed"
        ))
    ):
        return "found"

    # Evidence exists, but completion has not been established.
    if (
        status == "found"
        or validated
        or saved.get("candidate_urls")
        or evidence.get("directory_found")
        or evidence.get("directory_url")
        or has_records
    ):
        return "unconfirmed"

    return status or "unconfirmed"
