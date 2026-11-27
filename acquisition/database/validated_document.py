"""Retrieve previously validated directory documents."""

from pathlib import Path

import httpx


ROOT = Path(__file__).resolve().parents[2]


def get_validated_document(connection, result_id):
    """Return PDF content from a local file or validated source URL."""

    row = connection.execute("""
        SELECT url
        FROM search_results
        WHERE result_id = ?
          AND validation_status = 'VALIDATED'
    """, (result_id,)).fetchone()

    if row is None:
        raise ValueError(
            f"No validated document for result {result_id}"
        )

    path = ROOT / "documents" / "validated" / f"{result_id}.pdf"

    if path.is_file():
        content = path.read_bytes()
        source = "local"
    else:
        response = httpx.get(
            row[0],
            timeout=60,
            follow_redirects=True,
        )
        response.raise_for_status()
        content = response.content
        source = "download"

    if not content.startswith(b"%PDF-"):
        raise ValueError(
            f"Invalid PDF content for result {result_id}"
        )

    return content, source


def save_validated_document(result_id, content):
    """Retain the original bytes of a successfully validated PDF."""

    if not content.startswith(b"%PDF-"):
        raise ValueError(
            f"Invalid PDF content for result {result_id}"
        )

    directory = ROOT / "documents" / "validated"
    directory.mkdir(parents=True, exist_ok=True)

    path = directory / f"{int(result_id)}.pdf"
    temporary = path.with_suffix(".pdf.tmp")

    try:
        temporary.write_bytes(content)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)

    return path
