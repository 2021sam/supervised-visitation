"""Configuration-free extraction of labeled provider entries from PDFs."""

import pymupdf

from ..label_value_providers import extract_label_value_providers


def extract_pdf_label_value(
    pdf_bytes,
    *,
    start_page=0,
    source_url=None,
):
    """Extract contactable provider candidates from PDF text."""

    records = []

    with pymupdf.open(stream=pdf_bytes, filetype="pdf") as pdf:
        for page_index in range(start_page, len(pdf)):
            text = pdf[page_index].get_text(sort=True)

            for provider in extract_label_value_providers(text):
                name = (provider.get("name") or "").strip()
                phone = (provider.get("phone") or "").strip()
                email = (provider.get("email") or "").strip()

                if not name or not (phone or email):
                    continue

                records.append({
                    "page": page_index + 1,
                    "fields": provider,
                    "source_url": source_url,
                    "verified": False,
                })

    return records
