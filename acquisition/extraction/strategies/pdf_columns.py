"""Extract records from multi-column PDF tables using drawn row boundaries."""

import re
from dataclasses import dataclass

import pymupdf


EMAIL = re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")


@dataclass(frozen=True)
class PDFColumnsConfig:
    column_starts: tuple[float, ...]
    content_top: float = 45
    content_bottom: float = 740
    heading_patterns: tuple[str, ...] = ()
    anchor: str = "email"


def extract_pdf_columns(
    pdf_bytes: bytes,
    config: PDFColumnsConfig,
    *,
    start_page: int = 0,
    source_url: str | None = None,
) -> list[dict]:
    """Extract provider records from drawn PDF table cells."""

    if not config.column_starts:
        raise ValueError("At least one column is required")

    records = []

    with pymupdf.open(stream=pdf_bytes, filetype="pdf") as pdf:
        for page_index in range(start_page, len(pdf)):
            page = pdf[page_index]

            boundaries = sorted({
                round(drawing["rect"].y0, 1)
                for drawing in page.get_drawings()
                if (
                    drawing["rect"].width > 200
                    and drawing["rect"].height < 1
                    and config.content_top
                    <= drawing["rect"].y0
                    < config.content_bottom
                )
            })

            if not boundaries:
                continue

            boundaries.append(config.content_bottom)

            for top, bottom in zip(boundaries, boundaries[1:]):
                for column, left in enumerate(config.column_starts):
                    right = (
                        config.column_starts[column + 1] - 6
                        if column + 1 < len(config.column_starts)
                        else page.rect.width - 30
                    )

                    rect = pymupdf.Rect(
                        left, top + 1, right, bottom
                    )

                    lines = [
                        line.strip()
                        for line in page.get_text(
                            "text", clip=rect, sort=True
                        ).splitlines()
                        if line.strip()
                    ]

                    if not lines:
                        continue

                    if any(
                        re.search(pattern, lines[0], re.I)
                        for pattern in config.heading_patterns
                    ):
                        continue

                    email = next(
                        (
                            match.group()
                            for line in lines
                            if (match := EMAIL.search(line))
                        ),
                        None,
                    )

                    # Do not mistake unrelated table cells
                    # for provider records.
                    if config.anchor == "email" and not email:
                        continue

                    records.append({
                        "page": page_index + 1,
                        "column": column + 1,
                        "fields": {
                            "name": lines[0],
                            "email": email,
                            "raw_lines": lines,
                        },
                        "source_url": source_url,
                        "extraction_method": "pdf_columns",
                        "verified": False,
                    })

    return records
