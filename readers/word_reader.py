"""General-purpose DOC/DOCX extraction using the existing Apache Tika pipeline."""

import subprocess
import tempfile
from pathlib import Path


ENGINE_ROOT = Path.home() / "apps/data-acquisition-engine"
TIKA_PYTHON = ENGINE_ROOT / ".venv/bin/python"

SUPPORTED_EXTENSIONS = {".doc", ".docx"}


def extract_text(content: bytes, extension: str) -> str:
    """Extract Word document text through the existing Tika processor."""

    extension = extension.lower()

    if extension not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported Word format: {extension}")

    if not TIKA_PYTHON.is_file():
        raise RuntimeError(f"Tika environment unavailable: {TIKA_PYTHON}")

    with tempfile.TemporaryDirectory(prefix="word-reader-") as directory:
        path = Path(directory) / f"document{extension}"
        path.write_bytes(content)

        code = (
            "import sys; "
            "from acquisition.extraction.word_extractor import extract_word; "
            "print(extract_word(sys.argv[1]))"
        )

        result = subprocess.run(
            [str(TIKA_PYTHON), "-c", code, str(path)],
            cwd=ENGINE_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            raise RuntimeError(
                f"Tika extraction failed: {result.stderr.strip()}"
            )

        return result.stdout.strip()
