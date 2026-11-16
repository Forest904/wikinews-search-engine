from unittest.mock import Mock

import pytest
from elasticsearch.exceptions import ConnectionError, ConnectionTimeout

from wikinews_ir.config import Settings, get_settings
from wikinews_ir.retrieval.engine import RetrievalEngine


@pytest.mark.parametrize("timeout", [0, -1, float("inf"), float("nan")])
def test_invalid_timeout(timeout):
    with pytest.raises(ValueError, match="positive"):
        Settings(elasticsearch_timeout=timeout)


@pytest.mark.parametrize("failure", [ConnectionError("offline"), ConnectionTimeout("slow")])
def test_backend_failure(failure):
    engine = RetrievalEngine()
    engine.client.close()
    engine.client = Mock()
    engine.client.options.return_value.ping.side_effect = failure
    assert engine.check_ready() is False
    engine.client.options.assert_called_once_with(max_retries=0)


def test_environment_settings(monkeypatch):
    monkeypatch.setenv("ELASTICSEARCH_TIMEOUT", "2.5")
    get_settings.cache_clear()
    try:
        assert get_settings().elasticsearch_timeout == 2.5
    finally:
        get_settings.cache_clear()

@pytest.mark.parametrize("method", ["search", "get_article"])
@pytest.mark.parametrize("failure", [ConnectionError("offline"), ConnectionTimeout("slow")])
def test_retrieval_connection_failures(method, failure):
    from wikinews_ir.models import SearchRequest
    from wikinews_ir.retrieval.engine import RetrievalUnavailable

    backend = RetrievalEngine()
    backend.client.close()
    backend.client = Mock()
    backend.metadata = Mock(return_value={})
    getattr(backend.client, "get" if method == "get_article" else "search").side_effect = failure
    with pytest.raises(RetrievalUnavailable):
        getattr(backend, method)("demo-01" if method == "get_article" else SearchRequest(query="x"))


@pytest.mark.parametrize("method", ["search", "get_article"])
def test_backend_api_errors_are_sanitized(method):
    from elastic_transport import ApiResponseMeta, NodeConfig
    from elasticsearch.exceptions import ApiError

    from wikinews_ir.models import SearchRequest
    from wikinews_ir.retrieval.engine import RetrievalUnavailable

    backend = RetrievalEngine()
    backend.client.close()
    backend.client = Mock()
    backend.metadata = Mock(return_value={})
    failure = ApiError(
        "sensitive backend details",
        ApiResponseMeta(500, "1.1", {}, 0, NodeConfig("http", "localhost", 9200)),
        {"error": "sensitive backend details"},
    )
    getattr(backend.client, "get" if method == "get_article" else "search").side_effect = failure
    with pytest.raises(RetrievalUnavailable, match="Elasticsearch ha restituito un errore"):
        getattr(backend, method)("demo-01" if method == "get_article" else SearchRequest(query="x"))


def test_search_snippet_and_request_validation():
    from pydantic import ValidationError

    from wikinews_ir.models import SearchRequest

    backend = RetrievalEngine()
    backend.client.close()
    backend.client = Mock()
    backend.metadata = Mock(return_value={})
    backend.client.search.return_value = {
        "hits": {"total": {"value": 1}, "hits": [{
            "_id": "demo-01", "_score": 1.5,
            "_source": {"title": "Title", "body": "a" * 300, "url": "https://example.org"},
        }]}, "took": 3,
    }
    result = backend.search(SearchRequest(query=" title ", page_size=1))
    assert result.query == "title"
    assert result.hits[0].snippet == "a" * 240
    assert result.elapsed_ms == 3
    backend.client.search.reset_mock()
    request = SearchRequest(query="title")
    request.page_size = 101
    with pytest.raises(ValidationError):
        backend.search(request)
    backend.client.search.assert_not_called()
