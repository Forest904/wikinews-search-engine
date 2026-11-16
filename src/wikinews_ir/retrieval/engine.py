"""The same retrieval service will be reused by the API and experiments."""

from elasticsearch import Elasticsearch
from elasticsearch.exceptions import (
    ApiError,
    ConnectionTimeout,
)
from elasticsearch.exceptions import (
    ConnectionError as ElasticsearchConnectionError,
)

from wikinews_ir.config import Settings, get_settings
from wikinews_ir.models import Article, SearchHit, SearchRequest, SearchResponse
from wikinews_ir.retrieval.query_builder import build_query


class RetrievalUnavailable(RuntimeError):
    """Elasticsearch cannot be reached."""


class SearchIndexMissing(RuntimeError):
    """The requested index has not been created yet."""


class ArticleNotFound(RuntimeError):
    """The requested document does not exist."""


class RetrievalEngine:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.client = Elasticsearch(
            self.settings.elasticsearch_url,
            basic_auth=("elastic", self.settings.elastic_password),
            request_timeout=self.settings.elasticsearch_timeout,
        )

    def close(self) -> None:
        self.client.close()

    def check_ready(self) -> bool:
        try:
            return bool(self.client.options(max_retries=0).ping())
        except (ElasticsearchConnectionError, ConnectionTimeout, ApiError, OSError):
            return False

    def search(self, request: SearchRequest) -> SearchResponse:
        request = SearchRequest.model_validate(request.model_dump())
        body = build_query(request.query, request.profile)
        try:
            result = self.client.search(
                index=self.settings.elasticsearch_index,
                query=body,
                size=request.limit,
                track_total_hits=True,
            )
        except (ElasticsearchConnectionError, ConnectionTimeout) as exc:
            raise RetrievalUnavailable("Elasticsearch non raggiungibile") from exc
        except ApiError as exc:
            if exc.status_code == 404:
                raise SearchIndexMissing("Indice mancante: esegui seed-demo") from exc
            raise RetrievalUnavailable("Elasticsearch ha restituito un errore") from exc

        hits = [
            SearchHit(
                document_id=str(item["_id"]),
                rank=i,
                score=float(item.get("_score") or 0),
                title=item.get("_source", {}).get("title", ""),
                url=item.get("_source", {}).get("url", ""),
                snippet=item.get("_source", {}).get("body", "")[:240],
            )
            for i, item in enumerate(result["hits"]["hits"], start=1)
        ]
        return SearchResponse(
            query=request.query,
            profile=request.profile,
            index=self.settings.elasticsearch_index,
            hits=hits,
            total=int(result["hits"]["total"]["value"]),
            elapsed_ms=int(result.get("took", 0)),
        )

    def get_article(self, document_id: str) -> Article:
        try:
            result = self.client.get(index=self.settings.elasticsearch_index, id=document_id)
        except (ElasticsearchConnectionError, ConnectionTimeout) as exc:
            raise RetrievalUnavailable("Elasticsearch non raggiungibile") from exc
        except ApiError as exc:
            if exc.status_code == 404:
                error = exc.body.get("error", {}) if isinstance(exc.body, dict) else {}
                if isinstance(error, dict) and error.get("type") == "index_not_found_exception":
                    raise SearchIndexMissing("Indice mancante: esegui seed-demo") from exc
                raise ArticleNotFound("Articolo non trovato") from exc
            raise RetrievalUnavailable("Elasticsearch ha restituito un errore") from exc
        return Article.model_validate({**result["_source"], "document_id": str(result["_id"])})
