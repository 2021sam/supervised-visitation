"""Persistent SQLite storage for search mappings and raw API snapshots."""

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


SCHEMA = """
CREATE TABLE IF NOT EXISTS search_queries (
    id INTEGER PRIMARY KEY,
    cache_key TEXT NOT NULL UNIQUE,
    provider TEXT NOT NULL,
    query TEXT NOT NULL,
    parameters_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS search_responses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query_id INTEGER NOT NULL,
    fetched_at TEXT NOT NULL,
    fetched_epoch_ms INTEGER NOT NULL,
    response_json BLOB NOT NULL,
    response_sha256 TEXT NOT NULL,
    result_count INTEGER NOT NULL,
    FOREIGN KEY(query_id) REFERENCES search_queries(id)
);

CREATE INDEX IF NOT EXISTS idx_responses_query
ON search_responses(query_id, id);

CREATE TABLE IF NOT EXISTS api_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query_id INTEGER NOT NULL,
    attempted_at TEXT NOT NULL,
    status TEXT NOT NULL,
    error TEXT,
    FOREIGN KEY(query_id) REFERENCES search_queries(id)
);

CREATE INDEX IF NOT EXISTS idx_requests_query
ON api_requests(query_id, id);

CREATE TABLE IF NOT EXISTS search_claims (
    query_id INTEGER PRIMARY KEY,
    claimed_at TEXT NOT NULL,
    FOREIGN KEY(query_id) REFERENCES search_queries(id)
);


"""


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def cache_key(provider, query, parameters=None):
    """Identify a unique provider/query/parameter combination."""
    request = {
        "provider": provider,
        "query": query,
        "parameters": parameters or {},
    }
    encoded = json.dumps(
        request, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


class SearchCache:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

        self.con = sqlite3.connect(self.path, timeout=30)
        self.con.execute("PRAGMA busy_timeout=30000")
        self.con.execute("PRAGMA foreign_keys=ON")

        self.con.executescript(SCHEMA)

    def close(self):
        self.con.close()

    def _query_id(self, key):
        row = self.con.execute(
            "SELECT id FROM search_queries WHERE cache_key = ?",
            (key,),
        ).fetchone()

        if row is None:
            raise ValueError("Unknown search cache key")

        return row[0]

    def get_raw(self, key):
        """Retrieve the latest original response bytes."""
        row = self.con.execute(
            """
            SELECT r.response_json
            FROM search_responses r
            JOIN search_queries q ON q.id = r.query_id
            WHERE q.cache_key = ?
            ORDER BY r.id DESC
            LIMIT 1
            """,
            (key,),
        ).fetchone()

        return bytes(row[0]) if row else None

    def get(self, key):
        """Retrieve the latest JSON response as a Python object."""
        raw = self.get_raw(key)
        return json.loads(raw) if raw is not None else None

    def claim(self, provider, query, parameters=None, *, refresh=False):
        """Reserve a search, optionally refreshing an existing mapping."""
        parameters = parameters or {}
        key = cache_key(provider, query, parameters)

        self.con.execute("BEGIN IMMEDIATE")

        try:
            self.con.execute(
                """
                INSERT OR IGNORE INTO search_queries
                (cache_key, provider, query, parameters_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    key,
                    provider,
                    query,
                    json.dumps(parameters, sort_keys=True),
                    utc_now(),
                ),
            )

            query_id = self._query_id(key)

            if not refresh:
                existing = self.con.execute(
                    """
                    SELECT 1 FROM search_responses
                    WHERE query_id = ?
                    LIMIT 1
                    """,
                    (query_id,),
                ).fetchone()

                if existing:
                    self.con.commit()
                    return key, False

            cursor = self.con.execute(
                """
                INSERT OR IGNORE INTO search_claims
                (query_id, claimed_at)
                VALUES (?, ?)
                """,
                (query_id, utc_now()),
            )

            self.con.commit()
            return key, cursor.rowcount == 1

        except Exception:
            self.con.rollback()
            raise

    def save(self, key, response):
        """Persist original JSON bytes as a new immutable snapshot."""
        if not isinstance(response, bytes):
            raise TypeError("response must be original JSON bytes")

        payload = json.loads(response)

        if not isinstance(payload, dict):
            raise ValueError("API response must be a JSON object")

        count = len(payload.get("organic_results", []))
        digest = hashlib.sha256(response).hexdigest()

        instant = datetime.now(timezone.utc)
        fetched_at = instant.isoformat(timespec="milliseconds")
        fetched_epoch_ms = int(instant.timestamp() * 1000)

        with self.con:
            query_id = self._query_id(key)

            self.con.execute(
                """
                INSERT INTO search_responses
                (query_id, fetched_at, fetched_epoch_ms,
                 response_json, response_sha256, result_count)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    query_id,
                    fetched_at,
                    fetched_epoch_ms,
                    response,
                    digest,
                    count,
                ),
            )

            self.con.execute(
                """
                INSERT INTO api_requests
                (query_id, attempted_at, status)
                VALUES (?, ?, 'success')
                """,
                (query_id, fetched_at),
            )

            self.con.execute(
                "DELETE FROM search_claims WHERE query_id = ?",
                (query_id,),
            )

    def record_failure(self, key, error):
        """Record a failed attempt and release its claim."""
        with self.con:
            query_id = self._query_id(key)

            self.con.execute(
                """
                INSERT INTO api_requests
                (query_id, attempted_at, status, error)
                VALUES (?, ?, 'failed', ?)
                """,
                (query_id, utc_now(), str(error)),
            )

            self.con.execute(
                "DELETE FROM search_claims WHERE query_id = ?",
                (query_id,),
            )
