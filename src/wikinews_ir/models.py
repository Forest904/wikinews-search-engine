"""Stable public schemas shared between Web API and retrieval engine."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, field_validator, model_validator

from wikinews_ir.retrieval.profiles import ProfileId

SearchProfile = ProfileId | Literal["semantic"]


class SearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=1, max_length=250)
    profile: SearchProfile = "E0"
    year_from: int | None = Field(default=None, ge=1, le=9999)
    year_to: int | None = Field(default=None, ge=1, le=9999)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=10, ge=1, le=100)

    @model_validator(mode="after")
    def window(self):
        if self.year_from and self.year_to and self.year_from > self.year_to:
            raise ValueError("L’anno iniziale supera quello finale")
        if self.page * self.page_size > 10_000:
            raise ValueError("Paginazione limitata ai primi 10.000 risultati")
        if self.profile == "E4":
            from wikinews_ir.retrieval.query_builder import parse_phrases
            parse_phrases(self.query)
        return self

    @field_validator("query", mode="before")
    @classmethod
    def trim_query(cls, value):
        return value.strip() if isinstance(value, str) else value


class Article(BaseModel):
    _revision: str = PrivateAttr(default="")
    _checksum: str = PrivateAttr(default="")
    document_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    body: str = Field(min_length=1)
    url: str


class HighlightSegment(BaseModel):
    text: str
    highlighted: bool = False


class SearchHit(BaseModel):
    document_id: str
    rank: int
    score: float
    title: str
    url: str
    publication_date: str | None = None
    snippet: str = ""
    title_segments: list[HighlightSegment] = Field(default_factory=list)
    snippet_segments: list[HighlightSegment] = Field(default_factory=list)


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
