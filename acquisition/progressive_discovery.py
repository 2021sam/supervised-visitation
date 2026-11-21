"""Bounded, resumable discovery with AI-prioritized link traversal."""

import time
from contextlib import nullcontext
from urllib.parse import urlparse, urldefrag

from .crawl4ai_adapter import discover_with_crawl4ai
from .discovery_registry import DiscoveryRegistry
from .playwright_adapter import discover_with_playwright
from .semantic_client import SemanticClient
from .search_modes import get_search_mode


KEYWORDS = {
    "agree": 100,
    "continue": 100,
    "adm392": 100,
    "supervised visitation": 80,
    "provider": 60,
    "directory": 60,
    "visitation": 40,
    "resource": 10,
}


def score_link(entry):
    """Legacy ranking retained for compatibility and comparison."""
    content = (
        entry["url"] + " " + " ".join(entry["link_text"])
    ).lower()

    return sum(
        weight for keyword, weight in KEYWORDS.items()
        if keyword in content
    )


def is_document(url):
    """Recognize supported downloadable document formats."""
    return urlparse(url).path.lower().endswith(
        (".pdf", ".docx", ".doc")
    )


def crawl_progressively(
    start_url,
    *,
    registry_path,
    max_pages=None,
    max_depth=None,
    timeout_seconds=None,
    discover=discover_with_crawl4ai,
    fallback=None,
    ranker=None,
    progress_callback=None,
    search_mode="surface",
    traversal="dfs",
):
    """Discover links and visit them in AI relevance order.

    Production Crawl4AI runs use the persistent Python 3.12 AI worker.
    Injected rankers support deterministic tests.

    Legacy custom discovery functions retain keyword-based behavior
    unless a ranker is explicitly supplied.
    """
    mode = get_search_mode(search_mode)

    if timeout_seconds is not None and timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")

    deadline = (
        time.monotonic() + timeout_seconds
        if timeout_seconds is not None
        else None
    )
    timed_out = False

    def remaining_seconds():
        """Return the time left in this county's crawl budget."""
        if deadline is None:
            return None

        remaining = deadline - time.monotonic()

        if remaining <= 0:
            raise TimeoutError("County discovery deadline exceeded")

        return remaining

    registry = DiscoveryRegistry(registry_path)

    start_url, _ = urldefrag(start_url)
    registry.add(start_url, extractor="seed")

    ai_enabled = (
        ranker is not None
        or discover is discover_with_crawl4ai
    )

    if ranker is None and discover is discover_with_crawl4ai:
        ranker_context = SemanticClient(
            timeout_seconds=(
                min(60, remaining_seconds())
                if deadline is not None
                else 60
            )
        )
    else:
        ranker_context = nullcontext(ranker)

    queue = []
    queued = set()
    sequence = 0

    def enqueue(url, depth, score):
        nonlocal sequence

        if max_depth is not None and depth > max_depth:
            return

        entry = registry.data["links"].get(url)
        if entry is None or entry["status"] != "pending":
            return

        previous_depth = entry.get("depth")

        if previous_depth is None or depth < previous_depth:
            entry["depth"] = depth
            registry.save()

        if url in queued:
            return

        queued.add(url)
        sequence += 1
        queue.append((-score, depth, sequence, url))

    def rank_pending(client):
        """Rank newly discovered pending links and queue eligible URLs."""
        nonlocal registry

        registry = DiscoveryRegistry(registry_path)

        pending = []

        for entry in registry.pending():
            url = entry["url"]

            if is_document(url):
                registry.mark_status(
                    url, "document", engine="discovery"
                )
                continue

            if url in queued:
                continue

            depth = entry.get("depth")

            if depth is None:
                parent_depth = 0
                sources = entry.get("discovered_from", [])

                if sources:
                    parent_depth = min(
                        (
                            registry.data["links"].get(source, {})
                            .get("depth", 0)
                            for source in sources
                        ),
                        default=0,
                    )

                depth = parent_depth + 1

            if max_depth is not None and depth > max_depth:
                entry["depth"] = depth
                registry.save()
                continue

            pending.append(entry)

        if not pending:
            return

        if ai_enabled:
            missing = [
                entry for entry in pending
                if entry.get("semantic_score") is None
            ]

            if missing:
                if progress_callback is not None:
                    progress_callback(
                        5,
                        links_to_rank=len(missing),
                        pending_links=len(pending),
                        ranking_engine="minilm",
                    )

                remaining = remaining_seconds()

                if (
                    remaining is not None
                    and isinstance(client, SemanticClient)
                ):
                    client.timeout_seconds = min(60, remaining)

                scores = client.score_links(missing)

                if len(scores) != len(missing):
                    raise RuntimeError(
                        "AI returned an incorrect number of scores"
                    )

                for entry, score in zip(missing, scores):
                    entry["semantic_score"] = float(score)
                    entry["ranking_engine"] = "minilm"
                    entry["ranked_at"] = __import__(
                        "datetime"
                    ).datetime.now(
                        __import__("datetime").timezone.utc
                    ).isoformat()

                registry.save()

            for entry in pending:
                depth = entry.get("depth")

                if depth is None:
                    sources = entry.get("discovered_from", [])
                    parent_depth = min(
                        (
                            registry.data["links"].get(source, {})
                            .get("depth", 0)
                            for source in sources
                        ),
                        default=0,
                    )
                    depth = parent_depth + 1

                enqueue(
                    entry["url"],
                    depth,
                    entry.get("semantic_score", 0.0),
                )

        else:
            # Legacy scoring determines order, never eligibility.
            # Every discovered pending link remains searchable.
            for entry in pending:
                score = score_link(entry)
                depth = entry.get("depth", 1)
                enqueue(entry["url"], depth, score)

    visited = 0

    with ranker_context as client:
        registry = DiscoveryRegistry(registry_path)

        # The homepage is always the initial seed.
        seed = registry.data["links"][start_url]

        if seed["status"] == "pending":
            seed["depth"] = 0
            registry.save()

        try:
            if ai_enabled:
                rank_pending(client)
            else:
                enqueue(start_url, 0, 1000)
                rank_pending(client)
        except TimeoutError:
            timed_out = True

        while not timed_out and queue and (max_pages is None or visited < max_pages):
            if deadline is not None and time.monotonic() >= deadline:
                timed_out = True
                break

            registry = DiscoveryRegistry(registry_path)

            # Explicit DFS path. Reconstruct it from the most recently
            # visited page and its recorded discovery parents.
            if visited == 0:
                current_path = [start_url]

                if traversal == "dfs":
                    completed = []

                    for entry in registry.data["links"].values():
                        if entry["status"] != "visited":
                            continue

                        visits = [
                            event["timestamp"]
                            for event in entry.get("history", [])
                            if event.get("event") == "status_changed"
                            and event.get("status") == "visited"
                        ]

                        if visits:
                            completed.append(
                                (max(visits), entry["url"])
                            )

                    if completed:
                        _, latest_url = max(completed)

                        path_backwards = []
                        seen = set()
                        node = latest_url

                        while node not in seen:
                            seen.add(node)
                            path_backwards.append(node)

                            if node == start_url:
                                break

                            entry = registry.data["links"].get(
                                node, {}
                            )

                            parents = [
                                parent
                                for parent in entry.get(
                                    "discovered_from", []
                                )
                                if parent not in seen
                                and registry.data["links"].get(
                                    parent, {}
                                ).get("status") == "visited"
                            ]

                            if not parents:
                                break

                            def latest_visit(parent):
                                events = registry.data["links"][
                                    parent
                                ].get("history", [])

                                timestamps = [
                                    event["timestamp"]
                                    for event in events
                                    if event.get("event")
                                    == "status_changed"
                                    and event.get("status")
                                    == "visited"
                                ]

                                return max(timestamps, default="")

                            node = max(
                                parents,
                                key=lambda parent: (
                                    latest_visit(parent),
                                    parent,
                                ),
                            )

                        if path_backwards[-1] == start_url:
                            current_path = list(
                                reversed(path_backwards)
                            )

            def is_descendant(candidate_url, ancestor_url):
                """Check ancestry without following cycles indefinitely."""
                seen = set()
                pending_parents = [candidate_url]

                while pending_parents:
                    node = pending_parents.pop()

                    if node in seen:
                        continue

                    seen.add(node)

                    entry = registry.data["links"].get(node, {})

                    for parent in entry.get("discovered_from", []):
                        if parent == ancestor_url:
                            return True

                        if parent not in seen:
                            pending_parents.append(parent)

                return False

            # AI-guided DFS with relevance-aware backtracking.
            # Preserve branch continuity unless another pending link
            # has a substantially stronger semantic score.
            selected_index = None

            if traversal == "dfs":
                relevance_gap = 0.30

                best_global = min(
                    range(len(queue)),
                    key=lambda index: (
                        queue[index][0],
                        queue[index][2],
                    ),
                )

                for ancestor in reversed(current_path):
                    choices = [
                        index
                        for index, item in enumerate(queue)
                        if is_descendant(item[3], ancestor)
                    ]

                    if not choices:
                        continue

                    best_branch = min(
                        choices,
                        key=lambda index: (
                            queue[index][0],
                            queue[index][2],
                        ),
                    )

                    branch_score = -queue[best_branch][0]
                    global_score = -queue[best_global][0]

                    if global_score - branch_score > relevance_gap:
                        selected_index = best_global
                    else:
                        selected_index = best_branch

                    break

            # A pending homepage must be visited before its children.
            seed_index = next(
                (
                    index for index, item in enumerate(queue)
                    if item[3] == start_url
                    and registry.data["links"][start_url]["status"]
                    == "pending"
                ),
                None,
            )

            if seed_index is not None:
                selected_index = seed_index

            if selected_index is None:
                selected_index = min(
                    range(len(queue)),
                    key=lambda index: (
                        queue[index][0],
                        queue[index][2],
                    ),
                )

            if traversal == "bfs":
                # BFS: shallowest pages first, AI-ranked within each level.
                selected_index = min(
                    range(len(queue)),
                    key=lambda index: (
                        queue[index][1],
                        queue[index][0],
                        queue[index][2],
                    ),
                )
            elif traversal == "contextual_best_first" and seed_index is None:
                # Pure semantic best-first: rank each URL by its own score.
                # Parent scores remain discovery evidence, not ranking inputs.
                selected_index = min(
                    range(len(queue)),
                    key=lambda index: (
                        queue[index][0],
                        queue[index][2],
                    ),
                )

            elif traversal not in ("dfs", "contextual_best_first"):
                raise ValueError(
                    f"Unsupported traversal strategy: {traversal}"
                )

            _, depth, _, url = queue.pop(selected_index)

            # Keep the active ancestry available for backtracking.
            parents = registry.data["links"][url].get(
                "discovered_from", []
            )

            for index in range(len(current_path) - 1, -1, -1):
                if current_path[index] in parents:
                    current_path = current_path[:index + 1]
                    break
            else:
                current_path = []

            current_path.append(url)

            registry = DiscoveryRegistry(registry_path)
            entry = registry.data["links"].get(url)

            if entry is None or entry["status"] != "pending":
                continue

            if is_document(url):
                registry.mark_status(
                    url, "document", engine="discovery"
                )
                continue

            secondary = fallback

            if secondary is None and discover is discover_with_crawl4ai:
                secondary = discover_with_playwright

            engine = "crawl4ai"

            if progress_callback is not None:
                progress_callback(
                    6,
                    current_url=url,
                    pages_visited=visited,
                    unique_links=len(registry.data["links"]),
                    pending_links=len(registry.pending()),
                )

            try:
                if discover is discover_with_crawl4ai:
                    if progress_callback is not None:
                        progress_callback(
                            3,
                            current_url=url,
                            operation="discovering_navigation_controls",
                        )

                    remaining = remaining_seconds()
                    discover(
                        url,
                        registry_path=registry_path,
                        timeout_seconds=(
                            min(60, remaining)
                            if remaining is not None
                            else 60
                        ),
                        click_navigation=True,
                    )
                else:
                    remaining_seconds()
                    discover(url, registry_path=registry_path)

                remaining_seconds()

            except Exception as primary_error:
                if deadline is not None and time.monotonic() >= deadline:
                    timed_out = True
                    break
                if secondary is None:
                    registry = DiscoveryRegistry(registry_path)
                    registry.mark_status(
                        url,
                        "failed",
                        engine="crawl4ai",
                        reason=str(primary_error),
                    )
                    visited += 1
                    continue

                try:
                    remaining = remaining_seconds()

                    if secondary is discover_with_playwright:
                        secondary(
                            url,
                            registry_path=registry_path,
                            timeout_seconds=(
                                min(30, remaining)
                                if remaining is not None
                                else 30
                            ),
                        )
                    else:
                        secondary(
                            url,
                            registry_path=registry_path,
                        )

                    remaining_seconds()
                    engine = "playwright"

                except Exception as secondary_error:
                    if deadline is not None and time.monotonic() >= deadline:
                        timed_out = True
                        break
                    registry = DiscoveryRegistry(registry_path)
                    registry.mark_status(
                        url,
                        "failed",
                        engine="crawl4ai+playwright",
                        reason=(
                            f"Crawl4AI: {primary_error}; "
                            f"Playwright: {secondary_error}"
                        ),
                    )
                    visited += 1
                    continue

            registry = DiscoveryRegistry(registry_path)
            registry.mark_status(
                url, "visited", engine=engine
            )
            visited += 1

            # Compute depth from actual discovery parents.
            # Never assign depth based on an unrelated visited page.
            for candidate in registry.pending():
                parents = candidate.get("discovered_from", [])

                parent_depths = [
                    registry.data["links"][parent]["depth"]
                    for parent in parents
                    if parent in registry.data["links"]
                    and registry.data["links"][parent].get("depth")
                    is not None
                ]

                if not parent_depths:
                    continue

                candidate_depth = min(parent_depths) + 1
                previous_depth = candidate.get("depth")

                if (
                    previous_depth is None
                    or candidate_depth < previous_depth
                ):
                    candidate["depth"] = candidate_depth

            registry.save()

            if progress_callback is not None:
                progress_callback(
                    4,
                    current_url=url,
                    pages_visited=visited,
                    unique_links=len(registry.data["links"]),
                    pending_links=len(registry.pending()),
                )

            # Incorporate newly discovered links into the frontier.
            try:
                rank_pending(client)
            except TimeoutError:
                timed_out = True
                break

    registry = DiscoveryRegistry(registry_path)

    page_limit_hit = (
        max_pages is not None
        and not timed_out
        and visited >= max_pages
        and bool(queue)
    )

    depth_limit_hit = max_depth is not None and any(
        entry.get("status") == "pending"
        and entry.get("depth", 0) > max_depth
        for entry in registry.data["links"].values()
    )

    if timed_out:
        print(
            "WARNING: COUNTY TIMEOUT. Search is INCOMPLETE "
            "and can be resumed from the registry.",
            flush=True,
        )

    if page_limit_hit:
        print(
            f"WARNING: PAGE LIMIT HIT ({max_pages} pages). "
            "Search is INCOMPLETE.",
            flush=True,
        )

    if depth_limit_hit:
        print(
            f"WARNING: DEPTH LIMIT HIT ({max_depth}). "
            "Search is INCOMPLETE.",
            flush=True,
        )

    documents_identified = sum(
        entry["status"] == "document"
        for entry in registry.data["links"].values()
    )

    if progress_callback is not None:
        progress_callback(
            7,
            status="completed",
            documents_identified=documents_identified,
            unique_links=len(registry.data["links"]),
            pages_visited=visited,
            search_incomplete=(
                timed_out or page_limit_hit or depth_limit_hit
            ),
        )

    return {
        "ranking_engine": "minilm" if ai_enabled else "legacy",
        "traversal": traversal,
        "page_limit_hit": page_limit_hit,
        "depth_limit_hit": depth_limit_hit,
        "search_incomplete": (
            timed_out or page_limit_hit or depth_limit_hit
        ),
        "timed_out": timed_out,
        "pages_visited": visited,
        "total_unique_links": len(registry.data["links"]),
        "documents": [
            url for url, entry in registry.data["links"].items()
            if entry["status"] == "document"
        ],
        "failed": [
            url for url, entry in registry.data["links"].items()
            if entry["status"] == "failed"
        ],
        "pending": len(registry.pending()),
    }
