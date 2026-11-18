"""Public API schemas shared with Python callers."""

from pydantic import BaseModel

from wikinews_ir.models import Article, SearchHit, SearchRequest, SearchResponse

__all__ = ["Article", "SearchHit", "SearchRequest", "SearchResponse", "LiveSearchResponse"]


class Thumbnail(BaseModel):
    url: str
    width: int
    height: int
    artist: str
    license: str
    license_url: str
    source: str


class LiveHit(BaseModel):
    document_id: str
    pageid: int
    title: str
    snippet: str
    url: str
    local_url: str | None
    image: Thumbnail | None


class LiveSearchResponse(BaseModel):
    total: int
    hits: list[LiveHit]
    next_cursor: str | None
