"""Persistent JSON-lines interface for semantic link ranking."""

import json
import sys

from .semantic_ranker import score_links


def main():
    """Process ranking requests until stdin closes."""
    for line in sys.stdin:
        if not line.strip():
            continue

        try:
            request = json.loads(line)
            entries = request["entries"]

            if not isinstance(entries, list):
                raise ValueError("'entries' must be a list")

            scores = score_links(entries)

            response = {"scores": scores}

        except Exception as error:
            response = {"error": str(error)}

        print(json.dumps(response), flush=True)


if __name__ == "__main__":
    main()
