"""Stable public schemas shared between Web API and retrieval engine."""

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=250)
    profile: Literal["bm25"] = "bm25"
    limit: int = Field(default=10, ge=1, le=100)

    @field_validator("query", mode="before")
    @classmethod
    def trim_query(cls, value):
        return value.strip() if isinstance(value, str) else value


class Article(BaseModel):
    document_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    body: str = Field(min_length=1)
    url: str


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
