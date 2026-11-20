#!/usr/bin/env python3
"""
Reusable Crawl4AI search engine.

Interfaces:
    async_search()  - asynchronous Python API
    search()        - synchronous Python API
    main()          - command-line interface

Strategies:
    best-first      - prioritize relevant links
    bfs             - breadth-first search
    dfs             - depth-first search

No default page-count, depth, or overall search-time limits.
"""

import argparse
import asyncio
import heapq
import json
import re
from collections import deque
from urllib.parse import urljoin, urlparse, urldefrag, urlunparse

from bs4 import BeautifulSoup
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig


DOCUMENT_EXTENSIONS = (
    ".pdf", ".doc", ".docx", ".xls", ".xlsx"
)


def normalize_url(url):
    return urldefrag(url)[0]


def is_document(url):
    return urlparse(url).path.lower().endswith(
        DOCUMENT_EXTENSIONS
    )


def relevance_score(text, query):
    """
    Rank relevance using query coverage, consecutive
    phrases, and URL/link-text matches.

    Generic scoring: no supervised-visitation-specific
    keywords or hardcoded website paths.
    """
    words = re.findall(r"[a-z0-9]+", text.lower())
    query_words = re.findall(r"[a-z0-9]+", query.lower())

    if not query_words:
        return 0.0

    word_set = set(words)
    query_set = set(query_words)

    # How many distinct query terms appear?
    coverage = len(query_set & word_set) / len(query_set)

    # Reward consecutive query words.
    phrase_score = 0.0

    for length in range(2, len(query_words) + 1):
        for index in range(len(query_words) - length + 1):
            phrase = query_words[index:index + length]

            for position in range(len(words) - length + 1):
                if words[position:position + length] == phrase:
                    phrase_score += length * length
                    break

    # Longer matching phrases are more meaningful.
    normalized_phrase = phrase_score / max(
        1, sum(
            length * length * (len(query_words) - length + 1)
            for length in range(2, len(query_words) + 1)
        )
    )

    score = (
        0.65 * coverage
        + 0.35 * normalized_phrase
    )

    return round(score, 4)




class RelevanceRanker:
    """
    Generic keyword or hybrid semantic relevance ranking.

    MiniLM is loaded only when hybrid ranking is selected.
    """

    def __init__(self, query, mode="keyword"):
        if mode not in ("keyword", "hybrid"):
            raise ValueError("Unsupported ranking mode")

        self.query = query
        self.mode = mode
        self.model = None
        self.query_embedding = None
        self.cache = {}

        if mode == "hybrid":
            from sentence_transformers import SentenceTransformer

            self.model = SentenceTransformer(
                "sentence-transformers/all-MiniLM-L6-v2"
            )
            self.query_embedding = self.model.encode(
                query,
                normalize_embeddings=True,
            )

    def score(self, text):
        if text in self.cache:
            return self.cache[text]

        keyword = relevance_score(text, self.query)

        if self.mode == "keyword":
            score = keyword
        else:
            semantic = float(
                self.model.encode(
                    text,
                    normalize_embeddings=True,
                ) @ self.query_embedding
            )

            semantic = max(0.0, semantic)

            # Semantic similarity drives navigation relevance.
            # Strong lexical matches receive an additional bonus.
            # Weak isolated keyword matches do not override
            # semantically relevant navigation links.
            lexical_bonus = (
                0.25 * keyword
                if keyword >= 0.5
                else 0.0
            )

            score = min(
                1.0,
                semantic + lexical_bonus,
            )

        score = round(score, 4)
        self.cache[text] = score
        return score


def allowed_url(url, start_url, scope):
    parsed = urlparse(url)
    origin = urlparse(start_url)

    if parsed.scheme not in ("http", "https"):
        return False

    if scope == "external":
        return True

    if not parsed.hostname or not origin.hostname:
        return False

    host = parsed.hostname.lower()
    root = origin.hostname.lower()

    if scope == "subdomains":
        return host == root or host.endswith("." + root)

    return host == root


def extract_links(html, page_url):
    soup = BeautifulSoup(html, "html.parser")
    links = []

    for anchor in soup.select("a[href]"):
        href = anchor.get("href", "").strip()

        if not href:
            continue

        url = normalize_url(urljoin(page_url, href))
        text = anchor.get_text(" ", strip=True)

        links.append({
            "url": url,
            "text": text,
        })

    return links


async def async_search(
    url,
    query,
    strategy="best-first",
    scope="domain",
    max_pages=None,
    max_depth=None,
    dynamic=False,
    ranking="keyword",
):
    """
    Crawl from a starting URL and return structured results.

    Parameters:
        url: Starting URL
        query: Search relevance query
        strategy: best-first, bfs, dfs
        scope: domain, subdomains, external
        max_pages: Optional explicit page limit
        max_depth: Optional explicit depth limit
        dynamic: Enable JavaScript rendering/waiting
        ranking: keyword or hybrid

    Returns:
        dict containing pages visited, candidates,
        and crawl errors.
    """

    if strategy not in ("best-first", "bfs", "dfs"):
        raise ValueError("Unsupported search strategy")

    if scope not in ("domain", "subdomains", "external"):
        raise ValueError("Unsupported URL scope")

    if max_pages is not None and max_pages < 1:
        raise ValueError("max_pages must be positive")

    if max_depth is not None and max_depth < 0:
        raise ValueError("max_depth cannot be negative")

    start_url = normalize_url(url)

    if urlparse(start_url).scheme not in ("http", "https"):
        raise ValueError("Starting URL must use HTTP or HTTPS")

    ranker = RelevanceRanker(query, mode=ranking)

    # Learn redirect behavior from actual server responses.
    https_hosts = set()

    def canonical(url):
        url = normalize_url(url)
        parsed = urlparse(url)

        if (
            parsed.scheme == "http"
            and parsed.hostname
            and parsed.hostname.lower() in https_hosts
        ):
            parsed = parsed._replace(scheme="https")
            return urlunparse(parsed)

        return url

    visited = set()
    queued = {start_url}
    best_priorities = {start_url: 0.0}
    path_relevance = {start_url: 0.0}
    candidates = {}
    errors = []
    sequence = 0

    def rebuild_frontier():
        """Reconcile URL aliases without losing depth or relevance."""
        nonlocal queued, best_priorities, path_relevance
        nonlocal frontier, candidates

        priorities = {}
        relevance = {}

        for url, score in best_priorities.items():
            key = canonical(url)
            priorities[key] = max(score, priorities.get(key, 0.0))

        for url, score in path_relevance.items():
            key = canonical(url)
            relevance[key] = max(score, relevance.get(key, 0.0))

        best_priorities = priorities
        path_relevance = relevance

        old_visited = tuple(visited)
        visited.clear()
        visited.update(canonical(url) for url in old_visited)
        queued = {canonical(url) for url in queued}

        if strategy == "best-first":
            entries = {}

            for _, order, (url, depth) in frontier:
                key = canonical(url)

                if key in visited:
                    continue

                if key not in entries:
                    entries[key] = (order, depth)
                else:
                    old_order, old_depth = entries[key]
                    entries[key] = (
                        min(old_order, order),
                        min(old_depth, depth),
                    )

            frontier = [
                (-best_priorities[key], order, (key, depth))
                for key, (order, depth) in entries.items()
            ]
            heapq.heapify(frontier)

        else:
            entries = {}
            order = []

            for url, depth in frontier:
                key = canonical(url)

                if key in visited:
                    continue

                if key not in entries:
                    entries[key] = depth
                    order.append(key)
                else:
                    entries[key] = min(entries[key], depth)

            frontier = deque(
                (key, entries[key]) for key in order
            )

        merged_candidates = {}

        for url, candidate in candidates.items():
            key = canonical(url)
            updated = dict(candidate)
            updated["url"] = key
            updated["source_url"] = canonical(
                updated["source_url"]
            )

            existing = merged_candidates.get(key)

            if (
                existing is None
                or updated["score"] > existing["score"]
            ):
                merged_candidates[key] = updated

        candidates = merged_candidates

    if strategy == "best-first":
        frontier = []

        def push(item, score):
            nonlocal sequence
            heapq.heappush(
                frontier,
                (-score, sequence, item)
            )
            sequence += 1

        def pop():
            while frontier:
                negative_score, _, item = heapq.heappop(frontier)
                target = canonical(item[0])

                if target in visited:
                    continue

                if -negative_score < best_priorities[target]:
                    continue

                return target, item[1]

            return None

    else:
        frontier = deque()

        def push(item, score):
            frontier.append(item)

        if strategy == "dfs":
            def pop():
                return frontier.pop()
        else:
            def pop():
                return frontier.popleft()

    push((start_url, 0), 0.0)

    browser_config = BrowserConfig(
        headless=True
    )

    crawl_config = CrawlerRunConfig(
        page_timeout=30000,
        wait_for="css:body" if dynamic else None,
    )

    async with AsyncWebCrawler(
        config=browser_config
    ) as crawler:

        while frontier:
            if (
                max_pages is not None
                and len(visited) >= max_pages
            ):
                break

            item = pop()

            if item is None:
                break

            current_url, depth = item
            current_url = canonical(current_url)

            if current_url in visited:
                continue

            parent_relevance = path_relevance[current_url]
            visited.add(current_url)

            try:
                result = await crawler.arun(
                    url=current_url,
                    config=crawl_config,
                )

                if not result.success:
                    errors.append({
                        "url": current_url,
                        "error": str(result.error_message),
                    })
                    continue

                # Only learn a host-level HTTPS rule from a
                # successful, same-host, same-path redirect.
                requested = urlparse(current_url)
                final_url = normalize_url(
                    result.redirected_url or result.url
                )
                final = urlparse(final_url)

                if (
                    requested.scheme == "http"
                    and final.scheme == "https"
                    and requested.hostname == final.hostname
                    and requested.path == final.path
                    and requested.query == final.query
                    and result.status_code in (301, 308)
                    and result.redirected_status_code == 200
                ):
                    https_hosts.add(requested.hostname.lower())
                    rebuild_frontier()
                    current_url = canonical(current_url)

                # Resolve relative links against the final URL.
                page_url = final_url if final.scheme in (
                    "http", "https"
                ) else current_url

                links = extract_links(
                    result.html or "",
                    page_url,
                )

                for link in links:
                    original_target = link["url"]
                    target = canonical(original_target)

                    if not allowed_url(
                        target, start_url, scope
                    ):
                        continue

                    score = ranker.score(
                        link["text"] + " " + original_target
                    )

                    priority = max(
                        score,
                        0.75 * parent_relevance,
                    )

                    document = is_document(target)

                    if document:
                        existing = candidates.get(target)

                        candidate = {
                            "url": target,
                            "text": link["text"],
                            "score": score,
                            "source_url": current_url,
                            "depth": depth + 1,
                            "document": True,
                        }

                        if (
                            existing is None
                            or score > existing["score"]
                        ):
                            candidates[target] = candidate

                        continue

                    if (
                        max_depth is not None
                        and depth >= max_depth
                    ):
                        continue

                    if target in visited:
                        continue

                    if target not in queued:
                        queued.add(target)
                        best_priorities[target] = priority
                        path_relevance[target] = priority
                        push((target, depth + 1), priority)

                    elif (
                        strategy == "best-first"
                        and priority > best_priorities[target]
                    ):
                        best_priorities[target] = priority
                        path_relevance[target] = priority
                        push((target, depth + 1), priority)

                    existing = candidates.get(target)

                    candidate = {
                        "url": target,
                        "text": link["text"],
                        "score": score,
                        "source_url": current_url,
                        "depth": depth + 1,
                        "document": False,
                    }

                    if (
                        existing is None
                        or score > existing["score"]
                    ):
                        candidates[target] = candidate

            except Exception as exc:
                errors.append({
                    "url": current_url,
                    "error": str(exc),
                })

    ranked = sorted(
        candidates.values(),
        key=lambda item: (
            -item["score"],
            not item["document"],
            item["depth"],
        ),
    )

    return {
        "start_url": start_url,
        "query": query,
        "strategy": strategy,
        "scope": scope,
        "pages_visited": len(visited),
        "candidate_count": len(ranked),
        "candidates": ranked,
        "errors": errors,
    }


def search(**kwargs):
    """
    Synchronous Python API.

    Call async_search() instead when already inside
    an asynchronous event loop.
    """
    return asyncio.run(async_search(**kwargs))


def main():
    parser = argparse.ArgumentParser(
        description="Standalone Crawl4AI search engine"
    )

    parser.add_argument(
        "--url", required=True
    )

    parser.add_argument(
        "--query", required=True
    )

    parser.add_argument(
        "--strategy",
        choices=("best-first", "bfs", "dfs"),
        default="best-first",
    )

    parser.add_argument(
        "--scope",
        choices=("domain", "subdomains", "external"),
        default="domain",
    )

    parser.add_argument(
        "--max-pages",
        type=int,
        default=None,
    )

    parser.add_argument(
        "--max-depth",
        type=int,
        default=None,
    )

    parser.add_argument(
        "--dynamic",
        action="store_true",
    )

    parser.add_argument(
        "--ranking",
        choices=("keyword", "hybrid"),
        default="keyword",
    )

    parser.add_argument(
        "--json",
        action="store_true",
    )

    args = parser.parse_args()

    results = search(
        url=args.url,
        query=args.query,
        strategy=args.strategy,
        scope=args.scope,
        max_pages=args.max_pages,
        max_depth=args.max_depth,
        dynamic=args.dynamic,
        ranking=args.ranking,
    )

    if args.json:
        print(json.dumps(results, indent=2))
        return

    print(
        f"\nVisited: {results['pages_visited']} pages"
    )

    print(
        f"Candidates: {results['candidate_count']}\n"
    )

    for candidate in results["candidates"]:
        print(
            f"[{candidate['score']:.2f}] "
            f"{candidate['url']}"
        )

    if results["errors"]:
        print(
            f"\nCrawl errors: {len(results['errors'])}"
        )


if __name__ == "__main__":
    main()
