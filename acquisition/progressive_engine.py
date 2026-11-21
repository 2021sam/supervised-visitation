"""Adapt progressive AI discovery to the statewide crawler result format."""

import time
from urllib.parse import urlsplit
from pathlib import Path

from .discovery_registry import DiscoveryRegistry
from .semantic_client import SemanticClient
from .progressive_discovery import crawl_progressively
from .search_first.serpapi_provider import SerpApiProvider
from .search_first.registry_adapter import register_search_results


def classify_directory_evidence(url, link_text):
    """Classify explicit directory evidence without excluding documents."""
    import re

    evidence = f"{url} {link_text}".lower()
    evidence = re.sub(r"[_%20-]+", " ", evidence)

    visitation = re.search(
        r"supervised\s+visitation"
        r"|supervised\s+exchange"
        r"|visitation\s+monitor",
        evidence,
    )

    provider = re.search(
        r"provider|directory|professional\s+monitor",
        evidence,
    )

    if visitation and provider:
        return "relevant"

    return "uncertain"


def crawl_with_progressive(
    homepage,
    *,
    registry_path,
    max_pages=None,
    max_depth=None,
    timeout_seconds=None,
    progress_callback=None,
    search_mode="surface",
    traversal="dfs",
    search_queries=None,
):
    """Run AI-prioritized discovery and return statewide-compatible results."""

    registry_path = Path(registry_path)

    started = time.monotonic()

    if search_queries:
        provider = SerpApiProvider()
        for query in search_queries:
            results = provider.search(query)
            register_search_results(registry_path, results)

    discovery = crawl_progressively(
        homepage,
        registry_path=registry_path,
        max_pages=max_pages,
        max_depth=max_depth,
        timeout_seconds=timeout_seconds,
        progress_callback=progress_callback,
        search_mode=search_mode,
        traversal=traversal,
    )

    registry = DiscoveryRegistry(registry_path)

    # Score documents separately from page traversal.
    # All documents remain candidates regardless of relevance.
    documents_to_score = [
        registry.data["links"][url]
        for url in discovery["documents"]
        if registry.data["links"][url].get("semantic_score") is None
    ]

    if progress_callback is not None:
        progress_callback(
            8,
            documents_discovered=len(discovery["documents"]),
            documents_to_rank=len(documents_to_score),
            documents_previously_ranked=(
                len(discovery["documents"]) - len(documents_to_score)
            ),
        )

    if documents_to_score and not discovery.get("timed_out"):
        remaining = (
            timeout_seconds - (time.monotonic() - started)
            if timeout_seconds is not None
            else None
        )

        if remaining is None or remaining > 0:
            try:
                with SemanticClient(
                    timeout_seconds=(
                        min(60, remaining)
                        if remaining is not None
                        else 60
                    )
                ) as client:
                    scores = client.score_links(documents_to_score)

                if len(scores) != len(documents_to_score):
                    raise RuntimeError(
                        "Incorrect document semantic score count"
                    )

                for entry, score in zip(documents_to_score, scores):
                    entry["semantic_score"] = float(score)
                    entry["ranking_engine"] = "minilm"

                registry.save()

            except (TimeoutError, RuntimeError, OSError, ValueError) as error:
                print(
                    f"WARNING: PDF semantic ranking incomplete: {error}",
                    flush=True,
                )

    candidates = []

    for url in discovery["documents"]:
        entry = registry.data["links"][url]

        link_text = " ".join(entry.get("link_text", []))

        candidates.append({
            "url": url,
            "text": link_text,
            "directory_evidence": classify_directory_evidence(
                url, link_text
            ),
            "source_type": Path(urlsplit(url).path).suffix.lower().lstrip("."),
            "found_on": (
                entry.get("discovered_from") or [None]
            )[0],
            "discovered_by": list(entry.get("discovered_by", [])),
            "source_host": urlsplit(url).hostname,
            "score": entry.get("semantic_score"),
        })

    candidates.sort(
        key=lambda item: (
            -(item["score"] if item["score"] is not None else -1),
            item["url"],
        )
    )

    documents_unranked = sum(
        candidate["score"] is None
        for candidate in candidates
    )
    document_ranking_complete = documents_unranked == 0

    if discovery.get("timed_out"):
        status = "timeout"
    elif discovery["page_limit_hit"]:
        status = "budget_exhausted"
    elif discovery["depth_limit_hit"]:
        status = "depth_limit_reached"
    elif (
        discovery["failed"]
        or discovery["pending"]
        or discovery["search_incomplete"]
        or not document_ranking_complete
    ):
        status = "completed_with_errors"
    else:
        status = "completed"

    return {
        "status": status,
        "engine": "progressive",
        "ranking_engine": discovery["ranking_engine"],
        "traversal": discovery.get("traversal", traversal),
        "pages_attempted": discovery["pages_visited"],
        "links_examined": discovery["total_unique_links"],
        "links_until_first_candidate": None,
        "candidates": candidates,
        "candidate_count": len(candidates),
        "documents_discovered": len(discovery["documents"]),
        "directory_lead_count": sum(
            item["directory_evidence"] == "relevant"
            for item in candidates
        ),
        "document_ranking_complete": document_ranking_complete,
        "documents_unranked": documents_unranked,
        "search_incomplete": discovery["search_incomplete"]
            or bool(discovery["failed"])
            or bool(discovery["pending"])
            or not document_ranking_complete,
        "timed_out": discovery.get("timed_out", False),
        "page_limit_hit": discovery["page_limit_hit"],
        "depth_limit_hit": discovery["depth_limit_hit"],
        "failed": discovery["failed"],
        "pending": discovery["pending"],
        "registry_path": str(registry_path),
    }


def acquire_search_first(
    homepage,
    *,
    registry_path,
    search_queries,
    acquire,
):
    """Acquire public-web search results before any website traversal.

    The caller supplies the existing document acquisition pipeline.
    This function does not classify official court-directory status.
    """
    from acquisition.search_first.registry_adapter import (
        register_search_results,
    )

    search_results = []
    for query in search_queries:
        search_results.extend(SerpApiProvider().search(query))

    register_search_results(registry_path, search_results)

    candidates = []
    seen = set()

    for result in search_results:
        if result.url in seen:
            continue

        seen.add(result.url)
        candidates.append({
            "url": result.url,
            "text": f"{result.title} {result.snippet}",
            "source_type": (
                "pdf"
                if result.url.lower().split("?")[0].endswith(".pdf")
                else "web"
            ),
            "found_on": None,
            "discovered_by": [result.provider],
            "source_host": urlsplit(result.url).hostname,
        })

    acquired = acquire(candidates) if candidates else []

    validated_records = sum(
        len(document.get("records") or [])
        for document in acquired
        if document.get("directory_validated")
    )

    return {
        "candidates": candidates,
        "acquired": acquired,
        "validated_record_count": validated_records,
        "crawl_skipped": validated_records > 0,
    }
