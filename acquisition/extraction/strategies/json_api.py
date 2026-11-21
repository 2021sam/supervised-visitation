"""Extract structured records from JSON documents and APIs."""

import json


def extract_json_records(
    content: bytes,
    *,
    records_path: str = "",
    source_url: str | None = None,
) -> list[dict]:
    """Extract dictionary records from a JSON array.

    records_path is a dot-separated path to an array.
    An empty path selects the document root.
    """
    try:
        document = json.loads(content)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError(f"Invalid JSON document: {exc}") from exc

    selected = document

    if records_path:
        for key in records_path.split("."):
            if not key or not isinstance(selected, dict) or key not in selected:
                raise ValueError(
                    f"JSON records path not found: {records_path}"
                )
            selected = selected[key]

    if not isinstance(selected, list):
        raise ValueError(
            f"JSON records path must resolve to an array: {records_path!r}"
        )

    records = []

    for index, item in enumerate(selected):
        if not isinstance(item, dict) or not item:
            continue

        records.append({
            "item": index,
            "fields": dict(item),
            "source_url": source_url,
            "extraction_method": "json_api",
            "verified": False,
        })

    return records
