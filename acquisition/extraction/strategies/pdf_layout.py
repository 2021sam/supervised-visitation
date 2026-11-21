"""Geometry-based extraction of alternating-row PDF tables."""

from dataclasses import dataclass
from typing import Mapping

import pymupdf


@dataclass(frozen=True)
class PDFLayoutConfig:
    columns: Mapping[str, tuple[float, float]]
    content_top: float = 80
    content_bottom: float = 570
    contact_column: str = "contact"
    minimum_row_width: float = 500
    minimum_row_height: float = 10
    boundary_tolerance: float = 1


def extract_pdf_rows(
    pdf_bytes: bytes,
    config: PDFLayoutConfig,
    *,
    start_page: int = 0,
    source_url: str | None = None,
) -> list[dict]:
    """Extract records using alternating shaded/unshaded rows.

    Returns records with page, fields, and source provenance.
    This strategy requires filled background rectangles.
    """

    if config.contact_column not in config.columns:
        raise ValueError("Contact column is not configured")

    records = []

    with pymupdf.open(
        stream=pdf_bytes,
        filetype="pdf",
    ) as pdf:

        for page_index in range(start_page, len(pdf)):
            page = pdf[page_index]

            rectangles = sorted(
                [
                    drawing["rect"]
                    for drawing in page.get_drawings()
                    if drawing["type"] == "f"
                    and drawing["rect"].width
                    > config.minimum_row_width
                    and drawing["rect"].height
                    > config.minimum_row_height
                    and drawing["rect"].y0
                    >= config.content_top
                    and drawing["rect"].y1
                    < config.content_bottom
                ],
                key=lambda rect: rect.y0,
            )

            if not rectangles:
                continue

            spans = []

            for block in page.get_text("dict")["blocks"]:
                for line in block.get("lines", []):
                    for span in line["spans"]:
                        value = span["text"].strip()
                        x, y = span["bbox"][:2]

                        if (
                            value
                            and config.content_top <= y
                            < config.content_bottom
                        ):
                            spans.append((x, y, value))

            contact_left, contact_right = (
                config.columns[config.contact_column]
            )

            contact_spans = sorted(
                [
                    (y, value)
                    for x, y, value in spans
                    if contact_left <= x < contact_right
                ]
            )

            if not contact_spans:
                continue

            regions = []

            if (
                contact_spans[0][0]
                < rectangles[0].y0
                - config.boundary_tolerance
            ):
                regions.append(
                    (
                        "plain",
                        config.content_top,
                        rectangles[0].y0,
                    )
                )

            for index, rect in enumerate(rectangles):
                regions.append(
                    ("shaded", rect.y0, rect.y1)
                )

                if index + 1 < len(rectangles):
                    next_rect = rectangles[index + 1]

                    if next_rect.y0 - rect.y1 > 2:
                        regions.append(
                            (
                                "plain",
                                rect.y1,
                                next_rect.y0,
                            )
                        )

            if (
                contact_spans[-1][0]
                >= rectangles[-1].y1
                - config.boundary_tolerance
            ):
                regions.append(
                    (
                        "plain",
                        rectangles[-1].y1,
                        config.content_bottom,
                    )
                )

            for kind, top, bottom in regions:
                fields = {
                    name: []
                    for name in config.columns
                }

                for x, y, value in spans:
                    if not (
                        top - config.boundary_tolerance
                        <= y
                        < bottom - config.boundary_tolerance
                    ):
                        continue

                    for name, (left, right) in (
                        config.columns.items()
                    ):
                        if left <= x < right:
                            fields[name].append(value)
                            break

                if not fields[config.contact_column]:
                    continue

                records.append(
                    {
                        "page": page_index + 1,
                        "row_type": kind,
                        "fields": fields,
                        "source_url": source_url,
                        "extraction_method": "pdf_layout",
                        "verified": False,
                    }
                )

    return records
