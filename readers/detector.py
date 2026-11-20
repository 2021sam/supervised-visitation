"""Identify document formats using signatures, MIME types, and URLs."""

from pathlib import Path
from urllib.parse import urlsplit
from zipfile import BadZipFile, ZipFile
from io import BytesIO


MIME_FORMATS = {
    "application/pdf": "pdf",
    "text/html": "html",
    "application/xhtml+xml": "html",
    "application/msword": "doc",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/vnd.ms-excel": "xls",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
    "text/csv": "csv",
    "application/json": "json",
    "text/plain": "txt",
}

EXTENSION_FORMATS = {
    ".pdf": "pdf",
    ".html": "html",
    ".htm": "html",
    ".doc": "doc",
    ".docx": "docx",
    ".xls": "xls",
    ".xlsx": "xlsx",
    ".csv": "csv",
    ".json": "json",
    ".txt": "txt",
}


def detect_format(content: bytes, content_type: str = "", url: str = "") -> str:
    """Return a normalized format name, or 'unknown'."""

    if not content:
        return "unknown"

    if content.startswith(b"%PDF-"):
        return "pdf"

    if content.startswith(bytes.fromhex("D0CF11E0A1B11AE1")):
        extension = Path(urlsplit(url).path).suffix.lower()
        mime = content_type.split(";", 1)[0].strip().lower()

        if extension == ".xls" or mime == "application/vnd.ms-excel":
            return "xls"

        if extension == ".doc" or mime == "application/msword":
            return "doc"

        return "unknown"

    if content.startswith(b"PK\x03\x04"):
        try:
            with ZipFile(BytesIO(content)) as archive:
                names = set(archive.namelist())

            if "word/document.xml" in names:
                return "docx"

            if "xl/workbook.xml" in names:
                return "xlsx"
        except (BadZipFile, OSError, ValueError):
            return "unknown"

    mime = content_type.split(";", 1)[0].strip().lower()
    extension = Path(urlsplit(url).path).suffix.lower()

    if mime in MIME_FORMATS:
        return MIME_FORMATS[mime]

    return EXTENSION_FORMATS.get(extension, "unknown")
