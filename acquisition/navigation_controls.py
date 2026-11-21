"""Identify browser navigation controls that may require JavaScript."""

from bs4 import BeautifulSoup


NAVIGATION_TERMS = (
    "agree",
    "continue",
    "view directory",
    "view list",
    "view providers",
    "proceed",
)


def find_navigation_controls(html):
    """Return candidate controls without executing JavaScript."""
    soup = BeautifulSoup(html, "html.parser")
    controls = []

    for element in soup.select(
        "button, input[type='button'], input[type='submit'], "
        "a:not([href]), [role='button']"
    ):
        label = (
            element.get("value")
            or element.get("aria-label")
            or element.get_text(" ", strip=True)
        ).strip()

        if not label:
            continue

        if not any(term in label.lower() for term in NAVIGATION_TERMS):
            continue

        controls.append({
            "tag": element.name,
            "label": label,
            "id": element.get("id"),
            "name": element.get("name"),
            "onclick": element.get("onclick"),
        })

    return controls
