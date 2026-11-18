"""The same retrieval service will be reused by the API and experiments."""

from threading import Lock

import httpx
from elasticsearch import Elasticsearch
from elasticsearch.exceptions import (
    ApiError,
    ConnectionTimeout,
)
from elasticsearch.exceptions import (
    ConnectionError as ElasticsearchConnectionError,
)
from elasticsearch.helpers import ScanError, scan

from wikinews_ir.archive import build_catalog
from wikinews_ir.config import Settings, get_settings
from wikinews_ir.ingestion.indexer import inspect_index
from wikinews_ir.models import Article, SearchHit, SearchRequest, SearchResponse
from wikinews_ir.retrieval.highlight import HIGHLIGHT, segments
from wikinews_ir.retrieval.profiles import SUPPORTED_PROFILES, digest, index_name, profile_config
from wikinews_ir.retrieval.query_builder import build_query


class RetrievalUnavailable(RuntimeError):
    """Elasticsearch cannot be reached."""


class SearchIndexMissing(RuntimeError):
    """The requested index has not been created yet."""


class ArticleNotFound(RuntimeError):
    """The requested document does not exist."""


class RetrievalEngine:
    def __init__(self, settings: Settings | None = None):
        self._archive_lock = Lock()
        self._archive_uuid = None
        self._archive = {}
        self.settings = settings or get_settings()
        self.client = Elasticsearch(
            self.settings.elasticsearch_url,
            basic_auth=("elastic", self.settings.elastic_password),
            request_timeout=self.settings.elasticsearch_timeout,
        )

    def archive(self):
        try:
            with self._archive_lock:
                meta = self.metadata("E0")
                if meta["index_uuid"] != self._archive_uuid:
                    hits = scan(self.client, index=meta["index"], query={
                        "_source": ["document_id", "title", "categories", "publication_date"],
                    })
                    catalog = build_catalog(hit["_source"] for hit in hits)
                    if (catalog[""].count != meta["document_count"]
                            or self.metadata("E0")["index_uuid"] != meta["index_uuid"]):
                        raise RetrievalUnavailable("Archivio in aggiornamento")
                    self._archive = catalog
                    self._archive_uuid = meta["index_uuid"]
                return self._archive
        except (ElasticsearchConnectionError, ConnectionTimeout, ApiError, ScanError) as exc:
            raise RetrievalUnavailable("Archivio non disponibile") from exc

    def close(self) -> None:
        self.client.close()

    def check_ready(self) -> bool:
        try:
            return bool(self.client.options(max_retries=0).ping())
        except (ElasticsearchConnectionError, ConnectionTimeout, ApiError, OSError):
            return False

    def metadata(self, profile):
        name = index_name(self.settings, profile)
        try:
            meta = inspect_index(self.client, name, profile)
        except ValueError as exc:
            raise RetrievalUnavailable(str(exc)) from exc
        config = profile_config(profile)
        return {**meta, "profile_version": config["version"], "profile_sha256": digest(config)}

    def readiness(self):
        try:
            metadata = {p: self.metadata(p) for p in ("E0", "E1")}
            for profile, meta in metadata.items():
                if self.client.count(index=meta["index"])["count"] != meta["document_count"]:
                    raise RetrievalUnavailable(f"Conteggio errato: {profile}")
            if any(metadata["E0"][key] != metadata["E1"][key] for key in (
                "corpus_sha256", "content_sha256", "document_count", "snapshot_id",
            )):
                raise RetrievalUnavailable("I profili usano corpus diversi")
            for profile in SUPPORTED_PROFILES[2:]:
                config = profile_config(profile)
                metadata[profile] = {**metadata["E1"], "profile_version": config["version"],
                                     "profile_sha256": digest(config)}
            return metadata
        except (ElasticsearchConnectionError, ConnectionTimeout, ApiError, ValueError) as exc:
            raise RetrievalUnavailable("Indici non pronti: esegui index build") from exc

    def search(self, request: SearchRequest) -> SearchResponse:
        request = SearchRequest.model_validate(request.model_dump())
        if request.profile == "semantic":
            from wikinews_ir.semantic import search
            try:
                return search(request)
            except (httpx.HTTPError, ValueError, KeyError) as exc:
                raise RetrievalUnavailable("Ricerca semantica temporaneamente indisponibile") from exc
        body = build_query(request.query, request.profile)
        bounds = {}
        if request.year_from:
            bounds["gte"] = f"{request.year_from:04d}-01-01"
        if request.year_to:
            bounds["lte"] = f"{request.year_to:04d}-12-31"
        if bounds:
            body = {"bool": {"must": [body], "filter": [{"range": {"publication_date": bounds}}]}}
        try:
            metadata = self.metadata(request.profile)
            result = self.client.search(
                index=index_name(self.settings, request.profile),
                query=body,
                highlight=HIGHLIGHT,
                size=request.page_size,
                from_=(request.page - 1) * request.page_size,
                sort=[{"_score": "desc"}, {"document_id": "asc"}],
                track_total_hits=True,
                allow_partial_search_results=False,
            )
            if result.get("timed_out") or result.get("_shards", {}).get("failed", 0):
                raise RetrievalUnavailable("Ricerca incompleta: riprovare")
        except (ElasticsearchConnectionError, ConnectionTimeout) as exc:
            raise RetrievalUnavailable("Elasticsearch non raggiungibile") from exc
        except ApiError as exc:
            if exc.status_code == 404:
                raise SearchIndexMissing("Indice mancante: esegui index build") from exc
            raise RetrievalUnavailable("Elasticsearch ha restituito un errore") from exc

        hits = [
            SearchHit(
                document_id=str(item["_id"]),
                rank=i,
                score=float(item.get("_score") or 0),
                title=item.get("_source", {}).get("title", ""),
                url=item.get("_source", {}).get("url", ""),
                publication_date=item.get("_source", {}).get("publication_date"),
                title_segments=segments(item.get("highlight", {}).get("title")),
                snippet_segments=segments(item.get("highlight", {}).get("body")),
                snippet=item.get("_source", {}).get("body", "")[:240],
            )
            for i, item in enumerate(result["hits"]["hits"], start=(request.page - 1) * request.page_size + 1)
        ]
        return SearchResponse(
            query=request.query,
            profile=request.profile,
            index=index_name(self.settings, request.profile),
            page=request.page, page_size=request.page_size, metadata=metadata,
            hits=hits,
            total=int(result["hits"]["total"]["value"]),
            elapsed_ms=int(result.get("took", 0)),
        )

    def archived_ids(self, ids, timeout):
        if not ids:
            return set()
        try:
            result = self.client.options(request_timeout=timeout, max_retries=0).mget(
                index=index_name(self.settings, "E0"), ids=ids, source=False)
        except (ElasticsearchConnectionError, ConnectionTimeout, ApiError):
            return set()
        return {doc["_id"] for doc in result["docs"] if doc.get("found")}

    def get_article(self, document_id: str, profile: str = "E0") -> Article:
        if profile == 'semantic':
            profile = 'E0'
        try:
            meta = self.metadata(profile)
            result = self.client.get(index=index_name(self.settings, profile), id=document_id)
        except (ElasticsearchConnectionError, ConnectionTimeout) as exc:
            raise RetrievalUnavailable("Elasticsearch non raggiungibile") from exc
        except ApiError as exc:
            if exc.status_code == 404:
                error = exc.body.get("error", {}) if isinstance(exc.body, dict) else {}
                if isinstance(error, dict) and error.get("type") == "index_not_found_exception":
                    raise SearchIndexMissing("Indice mancante: esegui index build") from exc
                raise ArticleNotFound("Articolo non trovato") from exc
            raise RetrievalUnavailable("Elasticsearch ha restituito un errore") from exc
        article = Article.model_validate({**result["_source"], "document_id": str(result["_id"])})
        article._revision = result["_source"].get("revision_id", "")
        article._checksum = meta.get("corpus_sha256", "")
        return article
