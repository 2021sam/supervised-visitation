"""Register external search results in the existing discovery registry."""

from acquisition.discovery_registry import DiscoveryRegistry


def register_search_results(registry_path, results):
    """Persist search-discovered URLs without inventing crawl parents.

    The search provider retains raw response evidence separately.
    This adapter records candidate URLs and their search provenance
    in the existing progressive discovery registry.
    """
    registry = DiscoveryRegistry(registry_path)
    registered = 0

    with registry.batch():
        for result in results:
            if registry.add(
                result.url,
                extractor=result.provider,
                link_text=f"{result.title} {result.snippet}".strip(),
            ):
                registered += 1

    return registered
