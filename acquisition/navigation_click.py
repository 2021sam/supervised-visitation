"""Generate constrained browser actions for navigation controls."""

import json
import re


SAFE_ID = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,127}$")

ALLOWED_LABELS = {
    "agree",
    "continue",
    "view directory",
    "view list",
    "view providers",
    "proceed",
}


def build_navigation_click(control):
    """Return JavaScript for one explicitly recognized button.

    Returns None when the control is not safe to automate.
    """
    if control.get("tag") != "button":
        return None

    label = control.get("label", "").strip().lower()

    if label not in ALLOWED_LABELS:
        return None

    element_id = control.get("id")

    if not isinstance(element_id, str):
        return None

    if not SAFE_ID.fullmatch(element_id):
        return None

    # Serialize the ID as a JavaScript string literal.
    identifier = json.dumps(element_id)

    return (
        "(() => {"
        f"const element = document.getElementById({identifier});"
        "if (!element || element.tagName !== 'BUTTON') return false;"
        "if (element.disabled) return false;"
        "if (element.closest('form')) return false;"
        "element.click();"
        "return true;"
        "})()"
    )
