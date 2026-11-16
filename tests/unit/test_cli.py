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
