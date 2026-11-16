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
