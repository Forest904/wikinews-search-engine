from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from wikinews_ir.api.main import create_app
from wikinews_ir.api.routes import engine
from wikinews_ir.cli import seed_demo
from wikinews_ir.models import SearchRequest
from wikinews_ir.retrieval.engine import ArticleNotFound, RetrievalEngine, SearchIndexMissing

pytestmark = pytest.mark.integration


def test_fixture_search_and_lookup(seeded_backend):
    backend = seeded_backend
    response = backend.search(SearchRequest(query="  terremoto  "))
    assert response.query == "terremoto"
    assert [hit.document_id for hit in response.hits] == ["demo-01"]
    assert response.hits[0].rank == 1
    assert response.hits[0].score > 0
    assert backend.search(SearchRequest(query="soccorsi")).hits[0].document_id == "demo-01"
    assert backend.search(SearchRequest(query="zzzznonpresente")).total == 0
    assert "soccorsi" in backend.get_article("demo-01").body
    with pytest.raises(ArticleNotFound):
        backend.get_article("missing")
    seed_demo(backend.settings)
    assert backend.client.count(index=backend.settings.elasticsearch_index)["count"] == 5
    app = create_app()
    app.dependency_overrides[engine] = lambda: backend
    with TestClient(app) as client:
        assert client.get("/api/search", params={"q": "terremoto"}).json()["hits"][0]["document_id"] == "demo-01"
        assert client.get("/api/articles/demo-01").json()["body"] == backend.get_article("demo-01").body


def test_missing_index(seeded_backend):
    backend = RetrievalEngine(replace(
        seeded_backend.settings, elasticsearch_index=seeded_backend.settings.elasticsearch_index + "-missing"
    ))
    try:
        with pytest.raises(SearchIndexMissing):
            backend.search(SearchRequest(query="calcio"))
        with pytest.raises(SearchIndexMissing):
            backend.get_article("demo-01")
    finally:
        backend.close()
