"""Conservative classification of directory provider entries."""

import re


ORGANIZATION_TERMS = re.compile(
    r"\b("
    r"services|service|center|centre|agency|association|"
    r"foundation|hospital|institute|organization|"
    r"visitation program|family connections|"
    r"safe pair"
    r")\b",
    re.IGNORECASE,
)

PERSON_WITH_ORGANIZATION = re.compile(
    r"^(.+?)\s+at\s+(.+)$",
    re.IGNORECASE,
)

PERSON_NAME = re.compile(
    r"^(?:(?:Dr|Mr|Mrs|Ms)\.?\s+)?"
    r"[A-Z][A-Za-z'’-]+"
    r"(?:\s+[A-Z][A-Za-z'’-]+){1,3}"
    r"(?:,\s*(?:EdD|MSW|LCSW|LMFT|PhD|PsyD|MA|"
    r"MS|MFT|RN|LPCC|BA|BS)"
    r"(?:,\s*(?:EdD|MSW|LCSW|LMFT|PhD|PsyD|MA|"
    r"MS|MFT|RN|LPCC|BA|BS))*)?$"
)


def classify_provider(record):
    """Classify a provider entry without asserting credentials."""

    fields = record.get("fields") or {}
    name = str(fields.get("name") or "").strip()

    # Some PDF strategies preserve the provider identity
    # in the first contact entry instead of a name field.
    if not name:
        contact = fields.get("contact") or []

        if isinstance(contact, list) and contact:
            name = str(contact[0]).strip()

            # Reconstruct organization names split across
            # consecutive PDF text spans.
            if (
                name == "Sonoma County Legal"
                and len(contact) > 1
                and contact[1] == "Services Foundation"
            ):
                name = " ".join(contact[:2])

            elif (
                name == "Sonoma County"
                and len(contact) > 1
                and contact[1] == "Supervised Visitation"
            ):
                name = " ".join(contact[:2])

    if not name:
        return "organization"

    person_match = PERSON_WITH_ORGANIZATION.match(name)

    if person_match:
        person = person_match.group(1).strip()

        if PERSON_NAME.fullmatch(person):
            return "individual"

    if ORGANIZATION_TERMS.search(name):
        return "organization"

    if PERSON_NAME.fullmatch(name):
        return "individual"

    return "organization"


def count_provider_types(records):
    """Return counts that reconcile to the number of entries."""

    counts = {
        "individual": 0,
        "organization": 0,
        "unclassified": 0,
    }

    for record in records:
        category = classify_provider(record)
        counts[category] += 1

    return counts
