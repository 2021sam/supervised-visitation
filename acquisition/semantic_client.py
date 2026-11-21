"""Persistent subprocess client for Python 3.12 semantic ranking."""

import json
import math
import os
import selectors
import subprocess
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
AI_PYTHON = PROJECT_ROOT / ".venv-ai" / "bin" / "python"


class SemanticClient:
    """Rank links through a persistent, isolated AI worker."""

    def __init__(self, timeout_seconds=60):
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")

        self.timeout_seconds = timeout_seconds
        self.process = None
        self._buffer = bytearray()

    def __enter__(self):
        if not AI_PYTHON.is_file():
            raise RuntimeError(
                f"AI environment not found: {AI_PYTHON}"
            )

        self.process = subprocess.Popen(
            [
                str(AI_PYTHON),
                "-m",
                "acquisition.semantic_worker",
            ],
            cwd=PROJECT_ROOT,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            bufsize=0,
        )
        return self

    def _read_response(self, deadline):
        """Read a complete JSON line within one absolute deadline."""
        with selectors.DefaultSelector() as selector:
            selector.register(
                self.process.stdout,
                selectors.EVENT_READ,
            )

            while True:
                newline = self._buffer.find(b"\n")

                if newline >= 0:
                    line = bytes(self._buffer[:newline])
                    del self._buffer[:newline + 1]
                    return json.loads(line.decode("utf-8"))

                remaining = deadline - time.monotonic()

                if remaining <= 0:
                    raise TimeoutError(
                        "Semantic worker response timed out"
                    )

                if not selector.select(remaining):
                    raise TimeoutError(
                        "Semantic worker response timed out"
                    )

                chunk = os.read(
                    self.process.stdout.fileno(),
                    65536,
                )

                if not chunk:
                    raise RuntimeError(
                        "Semantic worker stopped responding"
                    )

                self._buffer.extend(chunk)

                if len(self._buffer) > 10_000_000:
                    raise RuntimeError(
                        "Semantic worker response exceeds size limit"
                    )

    def _write_request(self, request, deadline):
        """Write the complete request without exceeding the deadline."""
        fd = self.process.stdin.fileno()
        view = memoryview(request)
        offset = 0

        os.set_blocking(fd, False)

        try:
            with selectors.DefaultSelector() as selector:
                selector.register(fd, selectors.EVENT_WRITE)

                while offset < len(view):
                    remaining = deadline - time.monotonic()

                    if remaining <= 0 or not selector.select(remaining):
                        raise TimeoutError(
                            "Semantic worker request timed out"
                        )

                    try:
                        written = os.write(fd, view[offset:])
                    except BlockingIOError:
                        continue

                    if written <= 0:
                        raise RuntimeError(
                            "Semantic worker stopped accepting requests"
                        )

                    offset += written
        finally:
            os.set_blocking(fd, True)

    def score_links(self, entries):
        """Score all supplied links without a relevance threshold."""
        if not entries:
            return []

        if self.process is None or self.process.poll() is not None:
            raise RuntimeError("Semantic worker is not running")

        deadline = time.monotonic() + self.timeout_seconds
        request = (
            json.dumps({"entries": entries}) + "\n"
        ).encode("utf-8")

        try:
            self._write_request(request, deadline)
            response = self._read_response(deadline)
        except TimeoutError:
            raise
        except (BrokenPipeError, OSError) as error:
            raise RuntimeError(
                "Semantic worker communication failed"
            ) from error

        if "error" in response:
            raise RuntimeError(response["error"])

        scores = response["scores"]

        if len(scores) != len(entries):
            raise RuntimeError(
                "Semantic worker returned wrong score count"
            )

        if not all(
            isinstance(score, (int, float))
            and math.isfinite(score)
            for score in scores
        ):
            raise RuntimeError(
                "Semantic worker returned invalid scores"
            )

        return scores

    def __exit__(self, exc_type, exc_value, traceback):
        if self.process is not None:
            process = self.process

            if process.poll() is None:
                process.terminate()

                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()

            if process.stdin:
                process.stdin.close()

            if process.stdout:
                process.stdout.close()

            self.process = None
            self._buffer.clear()
