"""Identify supervised-visitation provider-list sections in Docling Markdown."""

import re


PROVIDER_HEADING = re.compile(
    r"\b(?:"
    r"(?:professional\s+)?(?:providers?\s+of\s+)?"
    r"supervised\s+visitation\s+(?:providers?|monitors?)"
    r"|professional\s+providers?\s+of\s+supervised\s+visitation"
    r"|supervised\s+visitation\s+(?:provider|monitor)\s+"
    r"(?:list|directory)"
    r")\b",
    re.IGNORECASE,
)


def has_provider_directory_heading(markdown: str) -> bool:
    """Return whether Markdown contains an explicit provider-list heading."""
    for line in markdown.splitlines():
        stripped = line.strip()

        if not stripped:
            continue

        if stripped.startswith("#"):
            if PROVIDER_HEADING.search(stripped.lstrip("# ")):
                return True

        elif stripped.startswith("|"):
            cells = [
                cell.strip()
                for cell in stripped.strip("|").split("|")
            ]

            if cells and all(
                PROVIDER_HEADING.search(cell)
                for cell in cells
            ):
                return True

    return False


def isolate_provider_tables(markdown: str) -> str:
    """Return tables explicitly labeled as provider directories."""
    tables = []
    current = []

    def flush():
        if not current:
            return

        cells = [
            cell.strip()
            for cell in current[0].strip("|").split("|")
        ]

        if cells and all(
            PROVIDER_HEADING.fullmatch(cell)
            for cell in cells
        ):
            tables.append("\n".join(current))

    for line in markdown.splitlines():
        stripped = line.strip()

        if stripped.startswith("|"):
            current.append(stripped)
        else:
            flush()
            current.clear()

    flush()

    return "\n\n".join(tables)
