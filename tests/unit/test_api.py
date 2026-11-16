from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from wikinews_ir.api.main import app, create_app
from wikinews_ir.api.routes import engine
from wikinews_ir.models import SearchRequest


@pytest.fixture
def client():
    with TestClient(app) as client:
        yield client


def test_home_page_loads_without_elasticsearch(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Ricerca Wikinotizie" in response.text


def test_openapi_contains_search(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    assert "/api/search" in response.json()["paths"]


def test_unsupported_profile_rejected_before_backend_connection(client):
    response = client.get("/api/search", params={"q": "calcio", "profile": "unknown"})
    assert response.status_code == 422


@pytest.mark.parametrize("ready,status", [(True, 200), (False, 503)])
def test_health(client, ready, status):
    backend = Mock()
    backend.check_ready.return_value = ready
    app.dependency_overrides[engine] = lambda: backend
    try:
        response = client.get("/api/health")
        assert response.status_code == status
        expected = {"app": "ok", "elasticsearch": "ready" if ready else "unavailable"}
        assert response.json() == (expected if ready else {"detail": expected})
    finally:
        app.dependency_overrides.clear()


def test_assets(client):
    assert client.get("/static/style.css").status_code == 200
    assert client.get("/static/app.js").status_code == 200


def test_backend_lifecycle(monkeypatch):
    backend = Mock()
    factory = Mock(return_value=backend)
    monkeypatch.setattr("wikinews_ir.api.main.RetrievalEngine", factory)
    with TestClient(create_app()) as client:
        client.get("/api/health")
        client.get("/api/health")
        factory.assert_called_once_with()
        backend.close.assert_not_called()
    backend.close.assert_called_once_with()


@pytest.mark.parametrize("failure,status", [("missing", 404), ("offline", 503), (None, 200)])
def test_search_uses_shared_backend(client, failure, status):
    from wikinews_ir.retrieval.engine import RetrievalUnavailable, SearchIndexMissing

    backend = Mock()
    if failure:
        backend.search.side_effect = (
            SearchIndexMissing("missing")
            if failure == "missing"
            else RetrievalUnavailable("offline")
        )
    else:
        backend.search.return_value = {
            "query": "calcio",
            "profile": "bm25",
            "index": "test",
            "hits": [],
            "total": 0,
            "elapsed_ms": 1,
        }
    app.dependency_overrides[engine] = lambda: backend
    try:
        response = client.get("/api/search", params={"q": "calcio"})
        assert response.status_code == status
        backend.search.assert_called_once_with(SearchRequest(query="calcio"))
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize("params", [
    {"q": " "}, {"q": "x" * 251}, {"q": "x", "limit": 0},
    {"q": "x", "limit": 101}, {"q": "x", "profile": "fuzzy"}, {},
])
def test_invalid_search_never_calls_backend(client, params):
    backend = Mock()
    app.dependency_overrides[engine] = lambda: backend
    try:
        assert client.get("/api/search", params=params).status_code == 422
        backend.search.assert_not_called()
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize("path", ["/api/articles/demo-01", "/articles/demo-01"])
@pytest.mark.parametrize("failure,expected", [(None, 200), ("article", 404), ("index", 404), ("offline", 503)])
def test_article_routes(client, path, failure, expected):
    from wikinews_ir.models import Article
    from wikinews_ir.retrieval.engine import (
        ArticleNotFound,
        RetrievalUnavailable,
        SearchIndexMissing,
    )
    backend = Mock()
    if failure:
        backend.get_article.side_effect = {
            "article": ArticleNotFound("Articolo non trovato"),
            "index": SearchIndexMissing("Indice mancante"),
            "offline": RetrievalUnavailable("Backend non disponibile"),
        }[failure]
    else:
        backend.get_article.return_value = Article(
            document_id="demo-01", title="<script>alert(1)</script>",
            body="Testo completo", url="javascript:alert(1)",
        )
    app.dependency_overrides[engine] = lambda: backend
    try:
        response = client.get(path)
        assert response.status_code == expected
        if not failure and path.startswith("/articles/"):
            assert "<script>" not in response.text
            assert "javascript:" not in response.text
            assert "Testo completo" in response.text
    finally:
        app.dependency_overrides.clear()
