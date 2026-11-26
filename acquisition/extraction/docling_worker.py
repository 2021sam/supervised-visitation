"""Convert PDF bytes to Markdown using Docling exclusively."""

import sys
import tempfile
from pathlib import Path

from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.datamodel.accelerator_options import (
    AcceleratorOptions,
    AcceleratorDevice,
)
from docling.document_converter import (
    DocumentConverter,
    PdfFormatOption,
)


def main():
    pdf_bytes = sys.stdin.buffer.read()

    if not pdf_bytes.startswith(b"%PDF-"):
        raise ValueError("Input is not a PDF")

    with tempfile.TemporaryDirectory(prefix="docling-") as directory:
        path = Path(directory) / "document.pdf"
        path.write_bytes(pdf_bytes)

        options = PdfPipelineOptions()
        options.accelerator_options = AcceleratorOptions(
            device=AcceleratorDevice.CPU
        )
        converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(
                    pipeline_options=options
                )
            }
        )
        result = converter.convert(str(path))
        markdown = result.document.export_to_markdown()

        if not markdown.strip():
            raise RuntimeError("Docling returned empty Markdown")

        sys.stdout.write(markdown)


if __name__ == "__main__":
    main()
