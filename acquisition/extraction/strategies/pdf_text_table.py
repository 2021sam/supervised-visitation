"""Extract PDF tables using text alignment rather than drawn boundaries."""

import re
from dataclasses import dataclass

import pymupdf


@dataclass(frozen=True)
class PDFTextTableConfig:
    columns: dict[str, tuple[float, float]]
    anchor_column: str = "intake_fee"
    anchor_pattern: str = r"^\$\s*\d"
    content_top: float = 65
    content_bottom: float = 740
    alignment_tolerance: float = 2.0
    page_content_bottoms: dict[int, float] | None = None
    anchor_requires_contact_alignment: bool = True


def extract_pdf_text_table(
    pdf_bytes: bytes,
    config: PDFTextTableConfig,
    *,
    start_page: int = 0,
    source_url: str | None = None,
) -> list[dict]:
    """Extract records using aligned text positions."""

    if config.anchor_column not in config.columns:
        raise ValueError("Anchor column is not configured")

    records = []
    anchor_re = re.compile(config.anchor_pattern)

    with pymupdf.open(stream=pdf_bytes, filetype="pdf") as pdf:
        for page_index in range(start_page, len(pdf)):
            page = pdf[page_index]
            page_bottom = (config.page_content_bottoms or {}).get(
                page_index + 1, config.content_bottom
            )
            spans = []

            for block in page.get_text("dict")["blocks"]:
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        value = span["text"].strip()
                        x, y = span["bbox"][:2]

                        if value and config.content_top <= y < page_bottom:
                            spans.append((x, y, value))

            anchor_left, anchor_right = config.columns[config.anchor_column]

            contact_left, contact_right = config.columns["contact"]

            contact_positions = [
                y
                for x, y, value in spans
                if contact_left <= x < contact_right
                and not re.search(r"\d{3}[-.) ]*\d{3}", value)
                and "@" not in value
                and not value.startswith(".")
            ]

            anchors = sorted({
                y
                for x, y, value in spans
                if anchor_left <= x < anchor_right
                and anchor_re.search(value)
                and (
                    not config.anchor_requires_contact_alignment
                    or any(
                        abs(contact_y - y)
                        <= config.alignment_tolerance
                        for contact_y in contact_positions
                    )
                )
            })

            if not anchors:
                continue

            for index, top in enumerate(anchors):
                bottom = (
                    anchors[index + 1]
                    if index + 1 < len(anchors)
                    else page_bottom
                )

                fields = {}

                for name, (left, right) in config.columns.items():
                    values = [
                        (y, value)
                        for x, y, value in spans
                        if left <= x < right
                        and top - config.alignment_tolerance <= y
                        < bottom - config.alignment_tolerance
                    ]

                    fields[name] = [
                        value for _, value in sorted(values)
                    ]

                if not fields.get("contact"):
                    continue

                records.append({
                    "page": page_index + 1,
                    "fields": fields,
                    "source_url": source_url,
                    "extraction_method": "pdf_text_table",
                    "verified": False,
                })

    return records
