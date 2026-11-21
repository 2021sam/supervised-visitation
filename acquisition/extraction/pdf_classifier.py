"""Classify PDF document purpose using content evidence."""

import re
from dataclasses import dataclass

import pymupdf


@dataclass(frozen=True)
class PDFClassification:
    document_type: str
    interactive_fields: int
    reason: str


FORM_PATTERN = re.compile(
    r"declaration and request for inclusion"
    r"|application for inclusion"
    r"|complete and sign this form",
    re.I,
)

POLICY_PATTERN = re.compile(
    r"list policy"
    r"|policy establishes guidelines"
    r"|policy for inclusion on and removal",
    re.I,
)


def classify_pdf(content: bytes) -> PDFClassification:
    """Identify forms and policies using document-level evidence."""

    with pymupdf.open(
        stream=content,
        filetype="pdf",
    ) as document:

        first_page = document[0].get_text() if len(document) else ""

        interactive_fields = sum(
            len(list(page.widgets() or []))
            for page in document
        )

    # Interactive fields provide strong evidence of a fillable form.
    if interactive_fields >= 5:
        return PDFClassification(
            document_type="form",
            interactive_fields=interactive_fields,
            reason="Multiple interactive PDF form fields",
        )

    # Prioritize the document's title and introductory text.
    heading = first_page[:500]

    if POLICY_PATTERN.search(heading):
        return PDFClassification(
            document_type="policy",
            interactive_fields=interactive_fields,
            reason="Policy identified in document heading",
        )

    if FORM_PATTERN.search(heading):
        return PDFClassification(
            document_type="form",
            interactive_fields=interactive_fields,
            reason="Application identified in document heading",
        )

    return PDFClassification(
        document_type="unknown",
        interactive_fields=interactive_fields,
        reason="No conclusive form or policy evidence",
    )
