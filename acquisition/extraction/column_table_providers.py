"""Extract provider candidates from column-based Docling Markdown tables."""

import re

from acquisition.extraction.markdown_providers import parse_row
from acquisition.extraction.provider_fields import extract_website
from acquisition.extraction.contact_cleanup import (
    clean_contact_name,
    normalize_fragmented_email,
)


def extract_column_table_providers(markdown):
    providers = []
    columns = None
    active_contact_directory = False

    for line in markdown.splitlines():
        stripped = line.strip()

        # Markdown table separators are not data rows
        # and must not reset the active column mapping.
        if stripped.startswith("|") and re.fullmatch(
            r"[|:\-\s]+", stripped
        ):
            continue

        cells = parse_row(stripped)

        if not cells:
            # Markdown separator rows are not table boundaries.
            if re.fullmatch(r"[|:\-\s]+", line.strip()):
                continue

            # Preserve the table schema across page breaks and
            # blank lines. A new recognized header replaces it.
            continue

        normalized = [
            re.sub(r"\s+", " ", cell).strip().lower()
            for cell in cells
        ]

        # Recognize both rate-based and contact-directory tables.
        contact_directory = (
            len(cells) >= 4
            and any(
                "name and contact information" in c
                for c in normalized
            )
            and "email" in normalized
            and any("services offered" in c for c in normalized)
        )

        rate_directory = (
            len(cells) >= 4
            and (
                normalized[0] == "name"
                or normalized[0] == "provider"
                or normalized[0].endswith(" - provider")
            )
            and any(
                c == "fees" or c == "rates"
                or c.endswith(" - fees")
                or c.endswith(" - rates")
                for c in normalized
            )
            and any(
                c == "availability"
                or c == "hours"
                or c == "trustline"
                or c.endswith(" - availability")
                for c in normalized
            )
        )

        provider_information_directory = (
            len(cells) >= 4
            and normalized[0] == "provider information"
            and "intake fee" in normalized
            and "hourly fee" in normalized
        )

        authorized_provider_directory = (
            len(cells) >= 4
            and normalized[0] == "name of authorized provider"
            and "fees" in normalized
            and "locations served" in normalized
        )

        embedded_contact_directory = (
            len(cells) >= 6
            and normalized[0] == "name"
            and "intake fee" in normalized
            and "hourly fees" in normalized
            and (
                "counties served" in normalized
                or "geographical location served" in normalized
            )
        )

        if (
            embedded_contact_directory
            or contact_directory
            or rate_directory
            or provider_information_directory
            or authorized_provider_directory
        ):
            active_contact_directory = (
                contact_directory
                or provider_information_directory
                or embedded_contact_directory
            )
            columns = []

            for heading in normalized:
                if (
                    "name and contact information" in heading
                    or heading == "provider information"
                ):
                    columns.append("name")
                elif heading == "email":
                    columns.append("email")
                elif heading == "website":
                    columns.append("website")
                elif (
                    "contact" in heading
                    or "phone/email" in heading
                    or ("phone" in heading and "email" in heading)
                ):
                    columns.append("contact")
                elif "availability" in heading or "hours" in heading:
                    columns.append("availability")
                elif "fee" in heading or "rate" in heading:
                    columns.append("rates")
                elif (
                    "geographic" in heading
                    or "service area" in heading
                    or "locations served" in heading
                ):
                    columns.append("service_area")
                elif "trustline" in heading:
                    columns.append("trustline_id")
                elif "language" in heading:
                    columns.append("languages")
                elif "provider" in heading or heading == "name":
                    columns.append("name")
                else:
                    columns.append(None)

            continue

        # Ignore Markdown separator rows, including repeated
        # separators inside continuation tables.
        if cells and all(
            re.fullmatch(r":?-{3,}:?", cell.strip())
            for cell in cells
        ):
            continue

        if columns is None:
            continue

        # Docling may split one PDF table into continuation
        # sections with fewer trailing columns.
        if len(cells) < len(columns):
            cells = cells + [""] * (len(columns) - len(cells))
        elif len(cells) > len(columns):
            continue

        candidate = {}

        for key, value in zip(columns, cells):
            if key and value:
                candidate[key] = value

        name = candidate.get("name", "").strip()

        # Contact-directory rows can consist entirely of a phone
        # number or other continuation data. Preserve those rows
        # until the continuation-merging stage.
        if (not name or len(name) < 4) and not active_contact_directory:
            continue

        if active_contact_directory and not name:
            continue

        # Exclude repeated table headings.
        if "professional supervised visitation and" in name.lower():
            continue

        # Some directories place labeled contact information
        # directly inside the provider-name column.
        if "Phone:" in name or "Email:" in name:
            original_name = name

            name = re.split(
                r"\b(?:Phone|Email|Website):",
                original_name,
                maxsplit=1,
                flags=re.IGNORECASE,
            )[0].strip()

            candidate["name"] = name
            candidate["embedded_contact"] = original_name

        contact = candidate.pop("contact", "")

        if candidate.get("embedded_contact"):
            contact += " " + candidate.pop("embedded_contact")

        if active_contact_directory:
            name = normalize_fragmented_email(name)
            emails_in_name = re.findall(
                r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}",
                name,
            )
            if emails_in_name:
                candidate["email"] = emails_in_name[0]
                candidate["name"] = name.replace(
                    emails_in_name[0], ""
                ).strip()
                name = candidate["name"]

            phones_in_name = re.findall(
                r"(?:\+?1[\s.-]?)?"
                r"(?:\(\d{3}\)|\d{3})[\s.-]?"
                r"\d{3}[\s.-]?\d{4}",
                name,
            )

            if phones_in_name:
                candidate["phone"] = phones_in_name[0]
                candidate["name"] = re.sub(
                    r"(?:\+?1[\s.-]?)?"
                    r"(?:\(\d{3}\)|\d{3})[\s.-]?"
                    r"\d{3}[\s.-]?\d{4}",
                    "",
                    name,
                ).strip()

            name = clean_contact_name(candidate["name"])
            candidate["name"] = name
            contact += " " + candidate.get("email", "")

        emails = re.findall(
            r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}",
            contact,
        )

        phones = re.findall(
            r"(?:\+?1[\s.-]?)?"
            r"(?:\(\d{3}\)|\d{3})[\s.-]?"
            r"\d{3}[\s.-]?\d{4}",
            contact,
        )

        if emails:
            candidate["email"] = emails[0]

        if phones:
            candidate["phone"] = phones[0]

        # Websites may appear in either the contact column
        # or the provider-name column.
        website = (
            candidate.get("website")
            or extract_website(contact)
            or extract_website(name)
        )
        if website:
            candidate["website"] = website

        # Exclude repeated court notices and other non-provider rows.
        if name.lower().startswith(
            "only the named supervised visitation monitors"
        ):
            continue

        candidate["raw_text"] = line.strip()

        if active_contact_directory and providers:
            previous = providers[-1]
            fragment = candidate.get("name", "").strip()
            previous_name = previous.get("name", "").strip()

            # Read the original name cell because phone extraction
            # may already have removed a phone-only fragment.
            original_fragment = cells[columns.index("name")].strip()

            # Only merge within the same contact-directory table.
            previous_is_contact = previous.get(
                "_contact_directory", False
            )

            phone_only = bool(
                re.fullmatch(
                    r"(?:\+?1[\s.-]?)?"
                    r"(?:\(\d{3}\)|\d{3})[\s.-]?"
                    r"\d{3}[\s.-]?\d{4}",
                    original_fragment,
                )
            )

            generic_fragment = fragment.casefold() in {
                "services",
                "visitation",
                "monitoring",
                "health",
            }

            address_fragment = bool(
                re.search(
                    r"\b(?:CA\s+\d{5}|Suite|Street|Avenue)\b",
                    original_fragment,
                    re.IGNORECASE,
                )
            )

            # A continuation may contain a name suffix, contact
            # details, or an address. Never merge a row that clearly
            # introduces a separate provider.
            continuation = (
                previous_is_contact
                and (
                    phone_only
                    or generic_fragment
                    or (
                        address_fragment
                        and not previous.get("phone")
                    )
                )
            )

            if continuation:
                if generic_fragment:
                    previous["name"] = (
                        previous_name + " " + fragment
                    ).strip()
                elif address_fragment:
                    # "Health Vista, CA 92083" is a split
                    # business name followed by a city and ZIP.
                    suffix = re.split(
                        r"\bVista,?\s+CA\s+\d{5}\b",
                        fragment,
                        maxsplit=1,
                        flags=re.IGNORECASE,
                    )[0].strip()

                    if suffix:
                        previous["name"] = (
                            previous_name + " " + suffix
                        ).strip()

                for key in ("phone", "email", "website"):
                    if candidate.get(key) and not previous.get(key):
                        previous[key] = candidate[key]

                previous["raw_text"] += "\n" + candidate["raw_text"]
                continue

        candidate["_contact_directory"] = active_contact_directory
        providers.append(candidate)

    for provider in providers:
        provider.pop("_contact_directory", None)

    return providers
