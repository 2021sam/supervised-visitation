"""Reusable document downloading, detection, and text extraction."""

import csv
import io
import json
from dataclasses import dataclass

from .secure_downloader import download_document
from bs4 import BeautifulSoup

from .detector import detect_format


@dataclass
class Document:
    url: str
    format: str
    text: str
    content_type: str


def extract_content(
    content: bytes,
    *,
    content_type: str = "",
    url: str = "",
) -> Document:
    """Extract text from already-downloaded document bytes."""

    format_name = detect_format(content, content_type, url)

    if format_name == "pdf":
        from .pdf_reader import extract_text
        text = extract_text(content)

    elif format_name in ("doc", "docx"):
        from .word_reader import extract_text
        text = extract_text(content, f".{format_name}")

    elif format_name == "html":
        soup = BeautifulSoup(content, "html.parser")
        for element in soup(["script", "style", "noscript"]):
            element.decompose()
        text = soup.get_text("\n", strip=True)

    elif format_name == "json":
        data = json.loads(content.decode("utf-8-sig"))
        text = json.dumps(data, indent=2, ensure_ascii=False)

    elif format_name == "csv":
        decoded = content.decode("utf-8-sig")
        rows = csv.reader(io.StringIO(decoded))
        text = "\n".join(" | ".join(row) for row in rows)

    elif format_name == "txt":
        text = content.decode("utf-8-sig")

    else:
        raise ValueError(
            f"Unsupported document format: {format_name}"
        )

    return Document(
        url=url,
        format=format_name,
        text=text,
        content_type=content_type,
    )


def read_document(url: str) -> Document:
    """Securely download a document and extract its readable content."""

    final_url, content_type, content = download_document(url)

    return extract_content(
        content,
        content_type=content_type,
        url=final_url,
    )
