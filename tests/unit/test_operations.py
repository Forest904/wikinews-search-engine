import importlib.util
import sqlite3
import subprocess
from contextlib import closing
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from wikinews_ir.annotation import connect, create_user
from wikinews_ir.api.main import create_app
from wikinews_ir.operations import check_annotation, snapshot


def test_health_never_creates_or_migrates_database(tmp_path, monkeypatch):
    path = tmp_path / "missing.sqlite3"
    monkeypatch.setenv("ANNOTATION_DB", str(path))
    with TestClient(create_app()) as client:
        assert client.get("/api/health/live").status_code == 200
        assert client.get("/api/health/annotation").status_code == 503
        assert not path.exists()
        with connect(path):
            pass
        assert client.get("/api/health/annotation").status_code == 200
        with closing(sqlite3.connect(path)) as db:
            db.execute("PRAGMA user_version=99")
        response = client.get("/api/health/annotation")
        assert response.status_code == 503
        assert str(path) not in response.text


def test_snapshot_includes_wal_and_preserves_source(tmp_path):
    source = tmp_path / "live.sqlite3"
    with connect(source) as db:
        create_user(db, "validator", "long-password")
        check_annotation(source)
        payload = snapshot(source)
        restored = tmp_path / "restored.sqlite3"
        restored.write_bytes(payload)
        with closing(sqlite3.connect(restored)) as copy:
            assert copy.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            assert copy.execute("SELECT id FROM users").fetchone()[0] == "validator"
            assert copy.execute("SELECT count(*) FROM audit").fetchone()[0] == 1
        assert db.execute("SELECT count(*) FROM users").fetchone()[0] == 1


def test_pc_download_validates_and_does_not_publish_partial(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("backup_to_pc", Path("scripts/backup_to_pc.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    source = tmp_path / "source.sqlite3"
    with connect(source):
        pass
    payload = snapshot(source)

    def success(args, stdout, check):
        assert args[:3] == ["ssh", "-T", "newsfinder"]
        stdout.write(payload)

    monkeypatch.setattr(module.subprocess, "run", success)
    target = tmp_path / "copy.sqlite3"
    module.download("newsfinder", target)
    assert target.exists()
    with pytest.raises(ValueError):
        module.download("newsfinder", target)

    def failure(args, stdout, check):
        stdout.write(b"truncated")
        raise subprocess.CalledProcessError(1, args)

    monkeypatch.setattr(module.subprocess, "run", failure)
    failed = tmp_path / "failed.sqlite3"
    with pytest.raises(subprocess.CalledProcessError):
        module.download("newsfinder", failed)
    assert not failed.exists()
    assert failed.with_name(failed.name + ".partial").exists()
