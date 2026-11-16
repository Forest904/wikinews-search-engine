"""Safe, intentionally small search query builder for the initial vertical slice."""

from wikinews_ir.retrieval.profiles import SUPPORTED_PROFILES


def build_query(query: str, profile: str = "bm25") -> dict:
    if profile not in SUPPORTED_PROFILES:
        raise ValueError(f"Retrieval profile not implemented: {profile}")
    if not query.strip():
        raise ValueError("La query non può essere vuota")
    return {"multi_match": {"query": query.strip(), "fields": ["title", "body"]}}
