import os

import pytest
from fastapi.testclient import TestClient

from wikinews_ir.api.main import create_app
from wikinews_ir.config import Settings, get_settings
from wikinews_ir.retrieval.engine import RetrievalEngine

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_INTEGRATION") != "1",
        reason="Set RUN_INTEGRATION=1 with Elasticsearch running",
    ),
]


def test_authenticated_health():
    with TestClient(create_app()) as client:
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json() == {"app": "ok", "elasticsearch": "ready"}


def test_wrong_credentials():
    settings = get_settings()
    backend = RetrievalEngine(
        Settings(
            elasticsearch_url=settings.elasticsearch_url,
            elastic_password="intentionally-invalid-test-password",
        )
    )
    try:
        assert backend.check_ready() is False
    finally:
        backend.close()
