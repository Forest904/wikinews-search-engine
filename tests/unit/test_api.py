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
    assert "NewsFinder" in response.text


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
            "profile": "E0",
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
    {"q": " "}, {"q": "x" * 251}, {"q": "x", "page_size": 0},
    {"q": "x", "page_size": 101}, {"q": "x", "profile": "fuzzy"}, {},
    {"q": "x", "limit": 10}, {"q": "x", "page": 101, "page_size": 100},
])
def test_invalid_search_never_calls_backend(client, params):
    backend = Mock()
    app.dependency_overrides[engine] = lambda: backend
    try:
        assert client.get("/api/search", params=params).status_code == 422
        backend.search.assert_not_called()
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize("available", [True, False])
def test_readiness(client, available):
    from wikinews_ir.retrieval.engine import RetrievalUnavailable

    backend = Mock()
    backend.readiness.return_value = {"E0": {}, "E1": {}}
    if not available:
        backend.readiness.side_effect = RetrievalUnavailable("Indici non pronti")
    app.dependency_overrides[engine] = lambda: backend
    try:
        response = client.get("/api/ready")
        assert response.status_code == (200 if available else 503)
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


def test_search_article_archive_navigation(client, monkeypatch):
    from bs4 import BeautifulSoup
    from wikinews_ir.archive import build_catalog
    from wikinews_ir.models import Article

    backend = Mock()
    backend.get_article.return_value = Article(
        document_id="demo-01", title="Finale", body="Testo", url="https://it.wikinews.org/wiki/Finale"
    )
    backend.archive.return_value = build_catalog([
        dict(document_id="demo-01", title="Finale", categories=["Serie A 2012-2013 (calcio)"])
    ])
    monkeypatch.setitem(app.dependency_overrides, engine, lambda: backend)
    query = "q=calcio&profile=E0&page=2&page_size=10&year_from=2012"
    folder = "sport/calcio/serie-a/2012-2013"

    def open_article(params):
        response = client.get("/articles/demo-01?" + params)
        assert response.status_code == 200
        return BeautifulSoup(response.text, "html.parser")

    search = open_article(query)
    archive = open_article("folder=" + folder + "&page=2")
    assert search.select_one(".breadcrumbs").get_text(strip=True) == archive.select_one(".breadcrumbs").get_text(strip=True)
    assert [a["href"] for a in search.select(".breadcrumbs a")] == [
        "/", "/archivio", "/archivio/sport", "/archivio/sport/calcio",
        "/archivio/sport/calcio/serie-a", "/archivio/" + folder,
    ]
    assert search.select_one('[aria-label="Livello superiore"]')["href"] == "/archivio/" + folder
    assert archive.select_one('[aria-label="Livello superiore"]')["href"] == "/archivio/" + folder + "?page=2"
    assert search.select_one(".back-link")["href"] == "/?" + query

    backend.archive.return_value = build_catalog([])
    fallback = open_article(query)
    assert fallback.select_one(".breadcrumbs a:last-of-type").get_text(strip=True) == "Risultati"
    assert fallback.select_one(".breadcrumbs a:last-of-type")["href"] == "/?" + query


def test_static_assets_change_url_with_content(client, monkeypatch):
    from pathlib import Path

    from wikinews_ir.api.routes import static_asset

    original = static_asset("annotation.js")
    response = client.get("/annotate")
    assert original in response.text
    assert client.get(original).status_code == 200
    read_bytes = Path.read_bytes
    monkeypatch.setattr(Path, "read_bytes", lambda path: read_bytes(path) + b"\n// changed" if path.name == "annotation.js" else read_bytes(path))
    changed = static_asset("annotation.js")
    assert changed != original
    assert changed in client.get("/annotate").text
