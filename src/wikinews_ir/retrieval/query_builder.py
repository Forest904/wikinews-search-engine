"""Safe, intentionally small search query builder for the initial vertical slice."""

from wikinews_ir.retrieval.profiles import profile_config


def build_query(query: str, profile: str = "E0") -> dict:
    config = profile_config(profile)
    if not query.strip():
        raise ValueError("La query non può essere vuota")
    return {"multi_match": {"query": query.strip(), **{
        key: config[key] for key in ("fields", "type", "operator")
    }}}
