"""Extract PDF provider candidates exclusively through Docling."""

from .docling_adapter import pdf_to_markdown
from .markdown_providers import extract_providers
from .column_table_providers import extract_column_table_providers
from .label_value_providers import extract_label_value_providers
from .heading_providers import extract_heading_providers


EXTRACTORS = (
    extract_providers,
    extract_column_table_providers,
    extract_label_value_providers,
    extract_heading_providers,
)


def extract_docling_pdf(content: bytes, *, source_url=None):
    """Convert once with Docling, then extract provider candidates."""

    markdown = pdf_to_markdown(content)

    records = []
    seen = set()

    for extractor in EXTRACTORS:
        for record in extractor(markdown):
            name = record.get("name", "").strip().casefold()

            if not name or name in seen:
                continue

            seen.add(name)
            records.append(record)

    return records
