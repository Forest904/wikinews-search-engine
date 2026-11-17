"""Lifecycle safety checks without terminating real processes."""
import importlib.util
from pathlib import Path
from unittest.mock import Mock

import pytest

spec = importlib.util.spec_from_file_location("local_runtime", Path(__file__).resolve().parents[2] / "scripts/local_runtime.py")
local = importlib.util.module_from_spec(spec)
spec.loader.exec_module(local)


def test_remote_elasticsearch_rejected(monkeypatch):
    monkeypatch.setenv("ELASTICSEARCH_URL", "https://remote.example:9200")
    with pytest.raises(RuntimeError, match="localhost"):
        local.configuration()


def test_local_environment_preserves_existing_indices(monkeypatch):
    monkeypatch.setenv("ELASTICSEARCH_URL", "http://127.0.0.1:9200")
    monkeypatch.setenv("ELASTICSEARCH_INDEX", "existing-index")
    monkeypatch.setenv("ANNOTATION_COOKIE_SECURE", "1")
    env, _ = local.configuration()
    assert env["ELASTICSEARCH_INDEX"] == "existing-index"
    assert env["ANNOTATION_COOKIE_SECURE"] == "0"
    assert Path(env["ANNOTATION_DB"]) == local.ROOT / "data/annotation/annotation.sqlite3"


def test_foreign_listener_never_terminated(monkeypatch):
    monkeypatch.setattr(local, "processes", lambda: [{"ProcessId": 123, "ParentProcessId": 0, "ExecutablePath": "other.exe", "CommandLine": "other"}])
    monkeypatch.setattr(local, "read_state", lambda: None)
    monkeypatch.setattr(local, "listeners", lambda port: [123])
    run = Mock()
    monkeypatch.setattr(local.subprocess, "run", run)
    with pytest.raises(RuntimeError, match="PID 123"):
        local.stop_instance(8000)
    run.assert_not_called()


def test_stale_pid_not_terminated(monkeypatch, tmp_path):
    state_file = tmp_path / "state.json"
    state_file.write_text("{}")
    monkeypatch.setattr(local, "STATE", state_file)
    monkeypatch.setattr(local, "read_state", lambda: {"root": str(local.ROOT), "pid": 123, "created": "old", "port": 8000})
    monkeypatch.setattr(local, "processes", lambda: [{"ProcessId": 123, "Created": "new"}])
    monkeypatch.setattr(local, "listeners", lambda port: [])
    run = Mock()
    monkeypatch.setattr(local.subprocess, "run", run)
    local.stop_instance(8000)
    run.assert_not_called()
    assert not state_file.exists()


def test_reload_worker_resolves_to_checkout_parent(monkeypatch, tmp_path):
    parent = {"ProcessId": 100, "ParentProcessId": 0, "Created": "now", "ExecutablePath": str(local.PYTHON), "CommandLine": "python -m uvicorn wikinews_ir.api.main:app --reload"}
    child = {"ProcessId": 101, "ParentProcessId": 100, "Created": "now", "ExecutablePath": "python.exe", "CommandLine": "spawn worker"}
    monkeypatch.setattr(local, "STATE", tmp_path / "state.json")
    monkeypatch.setattr(local, "read_state", lambda: None)
    monkeypatch.setattr(local, "processes", lambda: [parent, child])
    monkeypatch.setattr(local, "listeners", Mock(side_effect=[[101], []]))
    run = Mock()
    monkeypatch.setattr(local.subprocess, "run", run)
    local.stop_instance(8000)
    run.assert_called_once_with(["taskkill", "/PID", "100", "/T", "/F"], check=True, capture_output=True)
