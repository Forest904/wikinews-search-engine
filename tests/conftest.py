import os
from dataclasses import replace
from uuid import uuid4

import pytest

from wikinews_ir.cli import seed_demo
from wikinews_ir.config import get_settings
from wikinews_ir.retrieval.engine import RetrievalEngine


def pytest_collection_modifyitems(items):
    for item in items:
        for marker, flag in (("integration", "RUN_INTEGRATION"), ("e2e", "RUN_E2E")):
            if marker in item.keywords and os.getenv(flag) != "1":
                item.add_marker(pytest.mark.skip(reason=f"Set {flag}=1 to run"))


@pytest.fixture
def seeded_backend():
    settings = replace(get_settings(), elasticsearch_index="test-m1-" + uuid4().hex)
    backend = RetrievalEngine(settings)
    try:
        assert backend.check_ready(), "Authenticated Elasticsearch is required"
        seed_demo(settings)
        yield backend
    finally:
        try:
            backend.client.options(ignore_status=404).indices.delete(
                index=settings.elasticsearch_index
            )
        finally:
            backend.close()
