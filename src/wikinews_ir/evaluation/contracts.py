"""Versioned benchmark contracts, independent of search and annotation UI."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator

Identifier = Annotated[str, Field(min_length=1, pattern=r"^\S+$")]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Topic(Contract):
    query_id: Identifier
    query: str = Field(min_length=1, max_length=250)
    information_need: str = Field(min_length=1)
    narrative: str = Field(min_length=1)
    relevance_criteria: dict[str, str]
    inclusion_criteria: list[str] = Field(default_factory=list)
    exclusion_criteria: list[str]
    type: Literal["event-specific", "topical", "entity-oriented", "multi-constraint"]
    theme: str = Field(min_length=1)
    temporal_constraints: dict
    event_family: Identifier
    split: Literal["calibration", "development", "test"]
    variants: list[str] = Field(default_factory=list)
    ambiguity_notes: list[str] = Field(default_factory=list)
    selection_rationale: str = ""

    @model_validator(mode="after")
    def rubric(self):
        if set(self.relevance_criteria) != {"0", "1", "2"} or not all(
            v.strip() for v in self.relevance_criteria.values()
        ):
            raise ValueError("Rubrica richiesta per 0/1/2")
        if not self.query.strip():
            raise ValueError("Query vuota")
        return self


class Protocol(Contract):
    version: Identifier
    status: Literal["draft", "frozen"] = "draft"
    topics_target: int = 40
    development_topics_target: int = 24
    test_topics_target: int = 16
    relevance_levels: list[int] = [0, 1, 2]
    qrels_sources: list[str] = ["human_gold", "llm_silver"]
    external_baseline: str = "wikinews_ranked_results"
    metrics: list[str] = ["nDCG@10", "P@5"]
    silver_mode: Literal["codex_chat"] = "codex_chat"

    @model_validator(mode="after")
    def levels(self):
        if self.relevance_levels != [0, 1, 2]:
            raise ValueError("Scala richiesta: 0/1/2")
        return self


class Document(Contract):
    document_id: Identifier
    revision_id: Identifier
    title: str
    body: str = Field(min_length=1)
    body_sha256: str
    publication_date: str | None
    publication_date_status: str
    publication_date_evidence: list[str]


class Provenance(Contract):
    run_id: Identifier
    rank: int = Field(ge=1)


class Candidate(Contract):
    query_id: Identifier
    document_id: Identifier
    revision_id: Identifier
    body_sha256: str
    provenance: list[Provenance]
    selection: list[str] = Field(default_factory=list)


class Evidence(Contract):
    field: Literal["body"] = "body"
    quote: str = Field(min_length=1)
    start: StrictInt | None = Field(default=None, ge=0)
    end: StrictInt | None = Field(default=None, ge=0)


class Judgment(Contract):
    judgment_id: Identifier
    query_id: Identifier
    document_id: Identifier
    revision_id: Identifier
    body_sha256: str
    protocol_version: Identifier
    source: Literal["codex_chat", "human"]
    annotator_id: Identifier
    judged_at: str
    status: Literal["judged", "needs_review"]
    grade: StrictInt | None = Field(ge=0, le=2)
    rationale: str = Field(min_length=1)
    evidence: list[Evidence]
    ambiguity_reason: str | None = None
    final: bool = False
    origin_judgment_ids: list[Identifier] = Field(default_factory=list)

    @model_validator(mode="after")
    def decision(self):
        from datetime import datetime

        if datetime.fromisoformat(self.judged_at).tzinfo is None:
            raise ValueError("judged_at deve includere il fuso orario")
        if self.status == "judged" and (self.grade is None or not self.evidence):
            raise ValueError("Giudizio graduato richiede grado ed evidenza")
        if self.status == "needs_review" and (
            self.grade is not None or not self.ambiguity_reason
        ):
            raise ValueError("Astensione richiede grado null e motivazione")
        if self.source == "codex_chat" and (self.final or self.origin_judgment_ids):
            raise ValueError("Silver non può essere una decisione gold finale")
        if self.source == "human" and self.final and not self.origin_judgment_ids:
            raise ValueError("Gold finale richiede riferimenti ai giudizi originali")
        return self
