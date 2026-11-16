from fastapi.testclient import TestClient

from wikinews_ir.api.main import app

client = TestClient(app)


def test_home_page_loads_without_elasticsearch():
    response = client.get("/")
    assert response.status_code == 200
    assert "Ricerca Wikinotizie" in response.text


def test_openapi_contains_search():
    response = client.get("/openapi.json")
    assert response.status_code == 200
    assert "/api/search" in response.json()["paths"]


def test_unsupported_profile_rejected_before_backend_connection():
    response = client.get("/api/search", params={"q": "calcio", "profile": "unknown"})
    assert response.status_code == 422
