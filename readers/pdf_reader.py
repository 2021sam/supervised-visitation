"""Read PDF provider directories using the existing Docling pipeline."""

import sys
from pathlib import Path

ENGINE_ROOT = Path.home() / "apps/data-acquisition-engine"
sys.path.insert(0, str(ENGINE_ROOT))

from src.acquisition.extraction.docling_pdf import extract_docling_pdf


def extract(content: bytes, *, source_url: str = None) -> list[dict]:
    """Extract provider records from PDF bytes using Docling."""
    return extract_docling_pdf(content, source_url=source_url)


def extract_text(content: bytes) -> str:
    """Extract general-purpose PDF text using the existing Docling pipeline."""
    from src.acquisition.extraction.docling_adapter import pdf_to_markdown

    return pdf_to_markdown(content)
