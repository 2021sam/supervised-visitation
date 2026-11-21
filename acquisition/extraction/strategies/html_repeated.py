"""Extract records from repeated HTML structures."""

from bs4 import BeautifulSoup


def extract_html_repeated(
    html: str | bytes,
    *,
    item_selector: str,
    field_selectors: dict[str, str],
    source_url: str | None = None,
) -> list[dict]:
    """Extract records using configured CSS selectors.

    No industry-specific assumptions are made.
    Records remain unverified.
    """
    if not item_selector:
        raise ValueError("An item selector is required")

    if not field_selectors:
        raise ValueError("Field selectors are required")

    soup = BeautifulSoup(html, "html.parser")
    records = []

    for index, item in enumerate(
        soup.select(item_selector), start=1
    ):
        fields = {}

        for field_name, selector in field_selectors.items():
            element = item.select_one(selector)

            fields[field_name] = (
                " ".join(element.stripped_strings)
                if element
                else None
            )

        if not any(fields.values()):
            continue

        records.append(
            {
                "item": index,
                "fields": fields,
                "source_url": source_url,
                "extraction_method": "html_repeated",
                "verified": False,
            }
        )

    return records
