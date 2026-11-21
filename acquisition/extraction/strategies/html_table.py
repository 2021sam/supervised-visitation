"""Extract structured records from HTML tables."""

from bs4 import BeautifulSoup


def extract_html_tables(
    html: str | bytes,
    *,
    source_url: str | None = None,
) -> list[dict]:
    """Extract records from tables with explicit column headers.

    Only direct table rows and cells are considered.
    Nested tables are not treated as part of the parent table.
    Records remain unverified.
    """
    soup = BeautifulSoup(html, "html.parser")
    records = []

    for table_index, table in enumerate(
        soup.find_all("table"), start=1
    ):
        rows = [
            row
            for row in table.find_all("tr")
            if row.find_parent("table") is table
        ]

        if not rows:
            continue

        headers = None

        for row_index, row in enumerate(rows, start=1):
            cells = row.find_all(
                ["th", "td"],
                recursive=False,
            )

            if not cells:
                continue

            values = [
                " ".join(cell.stripped_strings)
                for cell in cells
            ]

            if headers is None:
                if not all(
                    cell.name == "th"
                    for cell in cells
                ):
                    continue

                headers = values

                if (
                    len(headers) < 2
                    or len(set(headers)) != len(headers)
                    or any(not name for name in headers)
                ):
                    headers = None

                continue

            if len(values) != len(headers):
                continue

            if not any(values):
                continue

            if all(
                cell.name == "th"
                for cell in cells
            ):
                continue

            records.append(
                {
                    "table": table_index,
                    "row": row_index,
                    "fields": dict(zip(headers, values)),
                    "source_url": source_url,
                    "extraction_method": "html_table",
                    "verified": False,
                }
            )

    return records
