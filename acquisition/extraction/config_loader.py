"""Load document extraction configurations from YAML."""

from pathlib import Path

import yaml


def load_extraction_config(path: str | Path) -> dict:
    """Return document URL -> orchestrator configuration."""
    path = Path(path)
    data = yaml.safe_load(path.read_text())

    if not isinstance(data, dict):
        raise ValueError("Extraction configuration must be a mapping")

    configurations = {}

    for document in data.get("documents", []):
        url = document["url"]
        strategy = document["strategy"]

        if url in configurations:
            raise ValueError(f"Duplicate document URL: {url}")

        config = {
            "start_page": document.get("start_page", 0),
        }

        if strategy == "docling_pdf":
            pass

        elif strategy == "html_table":
            pass

        elif strategy == "html_repeated":
            config["item_selector"] = document["item_selector"]
            config["field_selectors"] = document["field_selectors"]

        else:
            raise ValueError(
                f"Unsupported configured strategy: {strategy}"
            )

        configurations[url] = config

    return configurations
