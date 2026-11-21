"""Extract text from Word documents using Apache Tika."""

from pathlib import Path

from tika import parser


SUPPORTED_EXTENSIONS = {".doc", ".docx"}


def extract_word(path: str | Path) -> str:
    """Extract readable text from a local Word document."""

    path = Path(path)

    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported Word document: {path}")

    if not path.is_file():
        raise FileNotFoundError(path)

    result = parser.from_file(
        str(path),
        headers={"X-Tika-Skip-Embedded": "true"},
        requestOptions={"timeout": 120},
    )

    if result.get("status") not in (None, 200):
        raise RuntimeError(
            f"Tika extraction failed: {result.get('status')}"
        )

    content = result.get("content") or ""

    return content.strip()
