"""Semantic relevance ranking for discovered court links."""

from functools import lru_cache


SEARCH_OBJECTIVES = (
    "Official court supervised visitation provider directory",
    "Court approved professional visitation monitor referral list",
    "Supervised parenting time and child custody resources",
    "Family court services supervised visitation information",
)


@lru_cache(maxsize=1)
def load_model():
    """Load the embedding model once per process."""
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(
        "sentence-transformers/all-MiniLM-L6-v2"
    )


@lru_cache(maxsize=1)
def objective_embeddings():
    """Cache embeddings for our search objectives."""
    return load_model().encode(
        SEARCH_OBJECTIVES,
        normalize_embeddings=True,
    )


def score_links(entries):
    """Return semantic scores for every entry, without filtering."""
    if not entries:
        return []

    model = load_model()

    descriptions = [
        " ".join([
            " ".join(entry.get("link_text") or []),
            entry["url"].replace("/", " ").replace("-", " "),
        ])
        for entry in entries
    ]

    embeddings = model.encode(
        descriptions,
        normalize_embeddings=True,
    )

    similarities = embeddings @ objective_embeddings().T

    return [
        float(row.max())
        for row in similarities
    ]
