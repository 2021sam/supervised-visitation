"""Persistent, cumulative URL discovery registry."""

import json
import os
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urldefrag

from .core import safe_public_url


class DiscoveryRegistry:
    """Preserve URL discoveries across multiple extraction engines."""

    def __init__(self, path):
        self.path = Path(path)
        self.data = {"schema_version": 1, "links": {}}
        self._batch_depth = 0
        self._batch_dirty = False

    def add(self, url, *, extractor, found_on=None, link_text=None):
        """Record a discovery without discarding previous evidence."""
        url, _ = urldefrag(url)
        safe_public_url(url)

        if found_on:
            found_on, _ = urldefrag(found_on)
            safe_public_url(found_on)

        if not extractor or not extractor.strip():
            raise ValueError("Extractor name is required")

        now = datetime.now(timezone.utc).isoformat()

        entry = self.data["links"].setdefault(
            url,
            {
                "url": url,
                "status": "pending",
                "discovered_by": [],
                "discovered_from": [],
                "link_text": [],
                "history": [],
            },
        )

        if extractor not in entry["discovered_by"]:
            entry["discovered_by"].append(extractor)

        if found_on and found_on not in entry["discovered_from"]:
            entry["discovered_from"].append(found_on)

        if link_text and link_text not in entry["link_text"]:
            entry["link_text"].append(link_text)

        entry["history"].append(
            {
                "event": "discovered",
                "extractor": extractor,
                "found_on": found_on,
                "link_text": link_text,
                "timestamp": now,
            }
        )

        self._save_or_defer()
        return entry

    def mark_status(self, url, status, *, engine=None, reason=None):
        """Update processing status while preserving discovery history."""
        if status not in {"pending", "visited", "failed", "document"}:
            raise ValueError(f"Unsupported discovery status: {status}")

        url, _ = urldefrag(url)
        if url not in self.data["links"]:
            raise KeyError(f"URL has not been discovered: {url}")

        entry = self.data["links"][url]
        entry["status"] = status
        entry["history"].append(
            {
                "event": "status_changed",
                "status": status,
                "engine": engine,
                "reason": reason,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )
        self._save_or_defer()
        return entry

    @contextmanager
    def batch(self):
        """Defer registry writes until the batch exits.

        Previously recorded discoveries are saved even if an exception
        interrupts the batch. The original exception still propagates.
        """
        self._batch_depth += 1
        try:
            yield self
        finally:
            self._batch_depth -= 1
            if self._batch_depth == 0 and self._batch_dirty:
                self.save()
                self._batch_dirty = False

    def _save_or_defer(self):
        """Preserve immediate writes outside a batch."""
        if self._batch_depth:
            self._batch_dirty = True
        else:
            self.save()

    def pending(self):
        """Return links that have not completed processing."""
        return [
            entry
            for entry in self.data["links"].values()
            if entry["status"] == "pending"
        ]

    def save(self):
        """Traversal state is in memory; SQLite owns durable state."""
        self._batch_dirty = False
