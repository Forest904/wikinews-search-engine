"""Stable public schemas shared between Web API and retrieval engine."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class SearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=1, max_length=250)
    profile: Literal["E0", "E1"] = "E0"
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=10, ge=1, le=100)

    @model_validator(mode="after")
    def window(self):
        if self.page * self.page_size > 10_000:
            raise ValueError("Paginazione limitata ai primi 10.000 risultati")
        return self

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
    page: int = 1
    page_size: int = 10
    metadata: dict = Field(default_factory=dict)
