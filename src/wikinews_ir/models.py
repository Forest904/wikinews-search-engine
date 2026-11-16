"""Stable public schemas shared between Web API and retrieval engine."""

from pydantic import BaseModel, Field


class SearchHit(BaseModel):
    document_id: str
    rank: int
    score: float
    title: str
    url: str
    snippet: str = ""


class SearchResponse(BaseModel):
    query: str
    profile: str
    index: str
    hits: list[SearchHit]
    total: int = 0
    elapsed_ms: int = Field(ge=0)
