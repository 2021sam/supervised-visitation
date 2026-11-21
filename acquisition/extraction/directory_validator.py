"""Validate whether extracted records resemble a provider directory."""

import re
from dataclasses import dataclass

CONTACT_PATTERN = re.compile(
    r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}"
    r"|(?:\+1[\s.-]?)?\(?\d{3}\)?[\s.-]*\d{3}[\s.-]*\d{4}"
)

CONTEXT_PATTERN = re.compile(
    r"supervised[\s_-]*(?:visitation|exchange)"
    r"|visitation[\s_-]*monitor"
    r"|professional[\s_-]*monitor",
    re.I,
)


@dataclass(frozen=True)
class DirectoryValidation:
    is_directory: bool
    record_count: int
    named_records: int
    contactable_records: int
    context_found: bool
    reason: str


def validate_provider_directory(
    records: list[dict],
    *,
    source_description: str = "",
) -> DirectoryValidation:
    """Evaluate directory evidence without verifying providers."""

    named = 0
    contactable = 0
    context_found = bool(CONTEXT_PATTERN.search(source_description))

    for record in records:
        fields = record.get("fields")
        if fields is None:
            fields = record
        if not isinstance(fields, dict):
            continue

        values = []
        for value in fields.values():
            if isinstance(value, list):
                values.extend(str(item) for item in value)
            elif value is not None:
                values.append(str(value))

        combined = " ".join(values)

        if CONTEXT_PATTERN.search(combined):
            context_found = True

        has_contact = bool(CONTACT_PATTERN.search(combined))

        # Look for a non-contact identity in a named/contact field.
        identity_values = []
        for key, value in fields.items():
            if re.search(
                r"name|provider|agency|organization|business|contact",
                key,
                re.I,
            ):
                if isinstance(value, list):
                    identity_values.extend(str(item) for item in value)
                elif value is not None:
                    identity_values.append(str(value))

        has_name = any(
            len(value.strip()) >= 3
            and not CONTACT_PATTERN.search(value)
            and not value.strip().lower().startswith(("http", "www."))
            for value in identity_values
        )

        named += int(has_name)
        contactable += int(has_contact)

    accepted = (
        named >= 2
        and contactable >= 2
        and context_found
    )

    return DirectoryValidation(
        is_directory=accepted,
        record_count=len(records),
        named_records=named,
        contactable_records=contactable,
        context_found=context_found,
        reason=(
            "Multiple identifiable, contactable providers in relevant context"
            if accepted
            else "Insufficient evidence of a provider directory"
        ),
    )
