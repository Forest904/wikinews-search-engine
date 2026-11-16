from unittest.mock import Mock

import pytest

from wikinews_ir.cli import seed_demo


def test_seed_closes_backend_on_failure(monkeypatch):
    backend = Mock()
    backend.check_ready.return_value = False
    monkeypatch.setattr("wikinews_ir.cli.RetrievalEngine", lambda: backend)
    with pytest.raises(RuntimeError, match="non disponibile"):
        seed_demo()
    backend.close.assert_called_once_with()

@pytest.mark.parametrize("invalid", ["duplicate", "empty"])
def test_invalid_fixture_rejected_before_writes(monkeypatch, tmp_path, invalid):
    import json

    backend = Mock()
    backend.check_ready.return_value = True
    monkeypatch.setattr("wikinews_ir.cli.RetrievalEngine", lambda: backend)
    monkeypatch.setattr("wikinews_ir.cli.ROOT", tmp_path)
    mapping = tmp_path / "configs/indices/standard.json"
    mapping.parent.mkdir(parents=True)
    mapping.write_text("{}")
    fixtures = tmp_path / "tests/fixtures/articles.json"
    fixtures.parent.mkdir(parents=True)
    article = {"document_id": "demo-01", "title": "Title", "body": "body", "url": ""}
    articles = [article, article] if invalid == "duplicate" else [{**article, "body": ""}]
    fixtures.write_text(json.dumps(articles))
    with pytest.raises(ValueError):
        seed_demo()
    backend.client.indices.create.assert_not_called()
    backend.close.assert_called_once_with()
