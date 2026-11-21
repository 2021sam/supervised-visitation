"""Run Crawl4AI in its isolated environment and persist discoveries."""

import json
import subprocess
from pathlib import Path
from urllib.parse import urlparse

from .core import safe_public_url

from .discovery_registry import DiscoveryRegistry


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CRAWL4AI_PYTHON = PROJECT_ROOT / ".venv-crawl4ai/bin/python"
CRAWL4AI_SCRIPT = PROJECT_ROOT / "scripts/crawl4ai_discover.py"


def discover_with_crawl4ai(
    url,
    *,
    registry_path,
    timeout_seconds=60,
    click_navigation=False,
):
    """Discover links with Crawl4AI and persist them in the registry."""

    safe_public_url(url)
    registry = DiscoveryRegistry(registry_path)

    command = [
        str(CRAWL4AI_PYTHON),
        str(CRAWL4AI_SCRIPT),
    ]
    if click_navigation:
        command.append("--click-navigation")
    command.append(url)

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        check=True,
    )

    # Crawl4AI may print initialization messages before its JSON output.
    payload = None

    for line in reversed(result.stdout.splitlines()):
        try:
            candidate = json.loads(line)
        except json.JSONDecodeError:
            continue

        if isinstance(candidate, dict) and "links" in candidate:
            payload = candidate
            break

    if payload is None:
        raise ValueError("Crawl4AI did not return a valid discovery payload")

    source_url = payload["source_url"]
    safe_public_url(url)
    safe_public_url(source_url)

    expected_host = urlparse(url).hostname
    if urlparse(source_url).hostname != expected_host:
        raise ValueError("Crawl4AI redirected outside the court hostname")

    saved = 0

    with registry.batch():
        for link in payload["links"]:
            target = link["url"]
            safe_public_url(target)

            if urlparse(target).hostname != expected_host:
                continue

            registry.add(
                target,
                extractor="crawl4ai",
                found_on=source_url,
                link_text=link.get("text"),
            )
            saved += 1

    return {
        "source_url": source_url,
        "engine": "crawl4ai",
        "links_discovered": len(payload["links"]),
        "links_saved": saved,
        "navigation_controls": payload.get("navigation_controls", []),
        "clicked_control": payload.get("clicked_control"),
        "click_error": payload.get("click_error"),
        "total_unique_links": len(registry.data["links"]),
        "registry_path": str(registry.path),
    }
