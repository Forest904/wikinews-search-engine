from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from wikinews_ir.api.main import app, create_app
from wikinews_ir.api.routes import engine


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
        backend.search.assert_called_once_with(query="calcio", profile="bm25", limit=10)
    finally:
        app.dependency_overrides.clear()
