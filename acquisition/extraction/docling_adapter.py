"""Mandatory Docling PDF conversion. No fallback readers."""

import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DOCLING_PYTHON = PROJECT_ROOT / ".venv" / "bin" / "python"


def pdf_to_markdown(content: bytes) -> str:
    """Convert PDF bytes using the dedicated Docling environment."""

    if not content.startswith(b"%PDF-"):
        raise ValueError("Invalid PDF input")

    if not DOCLING_PYTHON.is_file():
        raise RuntimeError(
            f"Docling environment unavailable: {DOCLING_PYTHON}"
        )

    try:
        result = subprocess.run(
            [
                str(DOCLING_PYTHON),
                "-m",
                "acquisition.extraction.docling_worker",
            ],
            input=content,
            capture_output=True,
            check=False,
            cwd=PROJECT_ROOT,
        )
    except OSError as exc:
        raise RuntimeError(f"Docling execution failed: {exc}") from exc

    if result.returncode != 0:
        error = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(
            f"Docling conversion failed: {error}"
        )

    markdown = result.stdout.decode("utf-8")

    if not markdown.strip():
        raise RuntimeError("Docling returned empty Markdown")

    return markdown
