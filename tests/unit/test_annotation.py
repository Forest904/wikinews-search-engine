import io
import json
import sqlite3
import zipfile
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from wikinews_ir.annotation import (
    authenticate,
    connect,
    create_user,
    import_packet,
    reset_password,
    save,
    tasks,
)
from wikinews_ir.annotation_cli import backup, demo_payload
from wikinews_ir.annotation_export import export_snapshot, write_export
from wikinews_ir.annotation_workflow import (
    activate_block,
    adjudicate,
    assign_review,
    create_block,
    dashboard,
    review_tasks,
)
from wikinews_ir.api.main import create_app
from wikinews_ir.evaluation.artifacts import encoded, file_sha, verify_bundle, write_bundle
from wikinews_ir.evaluation.silver import export_qrels


@pytest.fixture
def setup(tmp_path, monkeypatch):
    path = tmp_path / "annotation.sqlite3"
    monkeypatch.setenv("ANNOTATION_DB", str(path))
    packet = tmp_path / "packet"
    write_bundle(packet, "packet", {"packet.json": encoded(demo_payload())})
    with connect(path) as db:
        for user in ("alice", "bob", "carol"):
            create_user(db, user, "password-test", coordinator=user == "alice")
        packet_id = import_packet(db, packet)
    return path, packet_id, packet


def block(db, packet_id, overlap=4):
    result = create_block(db, "alice", packet_id, "demo-energia", "alice", "bob", overlap, "42")
    activate_block(db, "alice", result["block"]["id"])
    return result


def submission(db, packet_id, **changes):
    args = dict(user_id="alice", packet_id=packet_id, query_id="demo-energia", document_id="demo-1",
                expected_version=0, request_id=uuid4().hex, status="judged", grade=2,
                rationale="L'impianto è installato nella scuola.",
                evidence=[{"quote": "La scuola", "start": 0, "end": 9}])
    args.update(changes)
    return save(db, **args)


def key(packet_id):
    return packet_id, "demo-energia", "demo-1"


def test_password_revision_and_idempotency(setup):
    path, packet_id, _ = setup
    with connect(path) as db:
        block(db, packet_id)
        assert authenticate(db, "alice", "password-test")
        assert not authenticate(db, "alice", "wrong")
        assert not authenticate(db, "unknown", "password-test")
        assert submission(db, packet_id, request_id="first") == 1
        assert submission(db, packet_id, request_id="first") == 1
        with pytest.raises(RuntimeError):
            submission(db, packet_id)
        with pytest.raises(ValueError):
            submission(db, packet_id, request_id="first", rationale="Changed")
        with pytest.raises(ValueError):
            submission(db, packet_id, request_id="first", user_id="bob")
        with pytest.raises(PermissionError):
            submission(db, packet_id, user_id="carol")
        assert submission(db, packet_id, expected_version=1) == 2
        assert db.execute("SELECT count(*) FROM judgments").fetchone()[0] == 2
        assert db.execute("SELECT count(*) FROM decisions WHERE current=1").fetchone()[0] == 0


def test_unicode_evidence_abstention_and_defer(setup):
    path, packet_id, _ = setup
    with connect(path) as db:
        block(db, packet_id)
        body = demo_payload()["documents"][0]["body"]
        start = body.index("📚")
        for evidence in ([{"quote": "La scuola", "start": 0, "end": 999}],
                         [{"quote": "La scuola", "start": 0}],
                         [{"quote": "La scuola", "start": False, "end": 9}]):
            with pytest.raises(ValueError):
                submission(db, packet_id, evidence=evidence)
        with pytest.raises(ValueError):
            submission(db, packet_id, status="needs_review", grade=None, rationale=" ")
        with pytest.raises(ValueError):
            submission(db, packet_id, grade=True)
        assert submission(db, packet_id, evidence=[{"quote": "📚", "start": start, "end": start+1}]) == 1
        assert submission(db, packet_id, expected_version=1, status="deferred", grade=None,
                          rationale="Da rileggere") == 2
        own = next(t for t in tasks(db, "alice") if t["document"]["document_id"] == "demo-1")
        assert own["own_judgment"]["status"] == "deferred"
        assert own["own_judgment"]["rationale"] == "Da rileggere"
        assert own["own_judgment"]["evidence"][0]["quote"] == "La scuola"


def test_assignment_freeze_determinism_and_permissions(setup):
    path, packet_id, _ = setup
    with connect(path) as db:
        with pytest.raises(PermissionError):
            create_block(db, "bob", packet_id, "demo-energia", "alice", "bob", 2, "42")
        first = block(db, packet_id, overlap=2)
        second = create_block(db, "alice", packet_id, "demo-energia", "alice", "bob", 2, "42")
        assert first["assignments"] == second["assignments"]
        assert len(tasks(db, "alice")) == 4
        assert len(tasks(db, "bob")) == 2
        assert tasks(db, "carol") == []
        with pytest.raises(RuntimeError):
            activate_block(db, "alice", second["block"]["id"])
        assert activate_block(db, "alice", first["block"]["id"])["block"]["active"] == 1


def test_automatic_final_and_invalidated_revision(setup):
    path, packet_id, _ = setup
    with connect(path) as db:
        block(db, packet_id)
        submission(db, packet_id)
        submission(db, packet_id, user_id="bob")
        final = dict(db.execute("SELECT * FROM decisions WHERE current=1").fetchone())
        assert final["grade"] == 2 and final["actor"] is None and final["method"] == "automatic"
        assert len(json.loads(final["origins"])) == 2
        submission(db, packet_id, expected_version=1, grade=0)
        assert db.execute("SELECT count(*) FROM decisions WHERE current=1").fetchone()[0] == 0
        assert db.execute("SELECT count(*) FROM decisions").fetchone()[0] == 1
        assert len(dashboard(db, "alice")["pending_reviews"]) == 1


def test_review_independence_stale_basis_and_final_abstention(setup):
    path, packet_id, _ = setup
    with connect(path) as db:
        block(db, packet_id)
        submission(db, packet_id)
        submission(db, packet_id, user_id="bob", grade=0)
        assert review_tasks(db, "alice") == []
        with pytest.raises(PermissionError):
            assign_review(db, "alice", key(packet_id), "alice")
        assign_review(db, "alice", key(packet_id), "carol")
        task = review_tasks(db, "carol")[0]
        assert len(task["originals"]) == 2
        submission(db, packet_id, expected_version=1, grade=1)
        with pytest.raises(RuntimeError):
            adjudicate(db, "carol", key(packet_id), task["basis"], "stale", "judged", 1,
                       "Parziale", [{"quote":"La scuola", "start":0, "end":9}])
        task = review_tasks(db, "carol")[0]
        decision = adjudicate(db, "carol", key(packet_id), task["basis"], "final", "needs_review",
                             None, "Ambiguità irrisolta", [])
        assert adjudicate(db, "carol", key(packet_id), task["basis"], "final", "needs_review",
                          None, "Ambiguità irrisolta", []) == decision
        assert review_tasks(db, "carol") == []
        assert db.execute("SELECT status FROM decisions WHERE current=1").fetchone()[0] == "needs_review"
        submission(db, packet_id, expected_version=2, status="deferred", grade=None)
        assert db.execute("SELECT count(*) FROM decisions WHERE current=1").fetchone()[0] == 0


def test_export_compatible_history_and_pending(setup, tmp_path):
    path, packet_id, _ = setup
    with connect(path) as db:
        block(db, packet_id, overlap=0)
        submission(db, packet_id)
        submission(db, packet_id, expected_version=1, grade=1)
        submission(db, packet_id, document_id="demo-2", status="deferred", grade=None, evidence=[])
        snapshot = export_snapshot(db, "alice", packet_id, "calibration")
        assert len(snapshot["judgments"]) == 2  # latest original plus its final
        assert len(snapshot["history"]) == 3
        assert snapshot["metadata"]["pending"] == 1
        assert snapshot["metadata"]["unjudged"] == 3
        assert snapshot["provenance"][0]["reviewer"] is None
        with pytest.raises(PermissionError):
            export_snapshot(db, "bob", packet_id, "calibration")
    output = tmp_path / "export"
    write_export(snapshot, output)
    verify_bundle(output, "annotation-gold-export")
    qrels_manifest = json.loads((output / "qrels_manifest.json").read_text("utf-8"))
    assert qrels_manifest["metadata"]["judgments_sha256"] == file_sha(output / "judgments.jsonl")
    assert qrels_manifest["metadata"]["packet_sha256"] == file_sha(output / "packet.json")
    assert (output / "qrels_gold.tsv").read_text() == "demo-energia 0 demo-1 1\n"
    export_qrels(output, output / "judgments.jsonl", tmp_path / "reexport", "gold")
    assert (tmp_path / "reexport/qrels_gold.tsv").read_bytes() == (output / "qrels_gold.tsv").read_bytes()


def test_import_integrity_and_test_separation(setup, tmp_path):
    path, packet_id, packet = setup
    with connect(path) as db:
        assert import_packet(db, packet) == packet_id
        payload = deepcopy(demo_payload())
        payload["topics"][0]["split"] = "test"
        write_bundle(tmp_path / "draft-test", "packet", {"packet.json": encoded(payload)})
        with pytest.raises(ValueError):
            import_packet(db, tmp_path / "draft-test")
        payload["protocol"]["status"] = "frozen"
        write_bundle(tmp_path / "test", "packet", {"packet.json": encoded(payload)})
        test_id = import_packet(db, tmp_path / "test")
        with pytest.raises(PermissionError):
            export_snapshot(db, "alice", test_id, "test")
        assert export_snapshot(db, "alice", test_id, "test", True)["metadata"]["release_test"]
        with pytest.raises(ValueError):
            export_snapshot(db, "alice", test_id, "development")
        (packet / "packet.json").write_text("{}", encoding="utf-8")
        with pytest.raises(ValueError):
            import_packet(db, packet)


def test_concurrent_saves_restart_and_backup(setup, tmp_path):
    path, packet_id, _ = setup
    with connect(path) as db:
        block(db, packet_id)

    def write(user):
        with connect(path) as db:
            return submission(db, packet_id, user_id=user)

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert list(pool.map(write, ["alice", "bob"])) == [1, 1]
    with connect(path) as db:
        assert db.execute("SELECT count(*) FROM decisions WHERE current=1").fetchone()[0] == 1
    target = tmp_path / "backup.sqlite3"
    backup(path.resolve(), target.resolve())
    with connect(target) as restored:
        assert len(tasks(restored, "alice")) == 4
        assert restored.execute("SELECT count(*) FROM judgments").fetchone()[0] == 2
    with pytest.raises(ValueError):
        backup(path.resolve(), target.resolve())


def login(client, name="alice"):
    result = client.post("/api/annotation/login", json={"user_id":name,"password":"password-test"})
    assert result.status_code == 200
    client.headers["X-CSRF-Token"] = result.json()["csrf"]
    return result


def test_api_authorization_csrf_revocation_and_no_leaks(setup):
    path, packet_id, _ = setup
    with connect(path) as db:
        block(db, packet_id)
        submission(db, packet_id, user_id="bob", rationale="PRIVATE-BOB")
    with TestClient(create_app()) as client:
        assert client.get("/api/annotation/tasks").status_code == 401
        result = login(client)
        assert "HttpOnly" in result.headers["set-cookie"]
        response = client.get("/api/annotation/tasks")
        assert response.headers["cache-control"] == "no-store"
        assert "PRIVATE-BOB" not in response.text
        for forbidden in ('"rank"', '"provenance"', '"silver"', '"originals"'):
            assert forbidden not in response.text
        assert "PRIVATE-BOB" not in client.get("/api/annotation/dashboard").text
        client.headers.pop("X-CSRF-Token")
        assert client.post("/api/annotation/logout", json={}).status_code == 403
        client.headers["X-CSRF-Token"] = result.json()["csrf"]
        assert client.post("/api/annotation/logout", json={}, headers={"Origin":"https://evil.test"}).status_code == 403
        assert client.post("/api/annotation/logout", json={}).status_code == 200
        assert client.get("/api/annotation/tasks").status_code == 401
        login(client, "bob")
        assert client.get("/api/annotation/dashboard").status_code == 403
        assert client.post("/api/annotation/exports", json={"packet_id":packet_id,"split":"calibration"}).status_code == 403
        with connect(path) as db:
            reset_password(db, "bob", "replacement-password")
        assert client.get("/api/annotation/session").status_code == 401


def test_api_login_rate_limit_and_export_download(setup):
    path, packet_id, _ = setup
    with connect(path) as db:
        block(db, packet_id, overlap=0)
        submission(db, packet_id)
    with TestClient(create_app()) as client:
        for _ in range(10):
            assert client.post("/api/annotation/login", json={"user_id":"unknown","password":"wrong"}).status_code == 401
        assert client.post("/api/annotation/login", json={"user_id":"unknown","password":"wrong"}).status_code == 429
        login(client)
        result = client.post("/api/annotation/exports", json={"packet_id":packet_id,"split":"calibration"})
        assert result.status_code == 200
        with zipfile.ZipFile(io.BytesIO(result.content)) as archive:
            assert archive.read("qrels_gold.tsv") == b"demo-energia 0 demo-1 2\n"


def test_schema_upgrade_preserves_old_accounts(tmp_path):
    path = tmp_path / "legacy.sqlite3"
    old = sqlite3.connect(path)
    old.execute("CREATE TABLE users(id TEXT PRIMARY KEY,password TEXT NOT NULL,coordinator INTEGER)")
    old.execute("INSERT INTO users VALUES('legacy','unused',0)")
    old.commit()
    old.close()
    with connect(path) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 1
        assert db.execute("SELECT id FROM users").fetchone()[0] == "legacy"


def test_same_user_concurrent_write_has_one_winner(setup):
    path, packet_id, _ = setup
    with connect(path) as db:
        block(db, packet_id, overlap=0)

    def write(_):
        with connect(path) as db:
            try:
                submission(db, packet_id)
                return "saved"
            except RuntimeError:
                return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(write, range(2))) == ["conflict", "saved"]
    with connect(path) as db:
        assert db.execute("SELECT count(*) FROM judgments").fetchone()[0] == 1
        assert db.execute("SELECT count(*) FROM decisions WHERE current=1").fetchone()[0] == 1


def test_cli_init_import_user_backup_restore(tmp_path, monkeypatch, capsys):
    from wikinews_ir.cli import main

    path = tmp_path / "cli.sqlite3"

    def cli(*args):
        monkeypatch.setattr("sys.argv", ["wikinews-ir", "annotation", "--db", str(path), *args])
        main()
        return json.loads(capsys.readouterr().out)

    assert cli("init")["schema_version"] == 1
    monkeypatch.setenv("M5B_TEST_PASSWORD", "private-fixture-password")
    assert cli("create-user", "operator", "--coordinator", "--password-env", "M5B_TEST_PASSWORD")["user_id"] == "operator"
    packet = tmp_path / "demo"
    cli("demo-packet", "--output", str(packet))
    assert cli("import", "--packet", str(packet))["packet_id"]
    archive = tmp_path / "copy.sqlite3"
    assert cli("backup", "--output", str(archive))["integrity"] == "ok"
    restored = tmp_path / "restored.sqlite3"
    monkeypatch.setattr("sys.argv", ["wikinews-ir", "annotation", "--db", str(restored),
                                    "restore", "--input", str(archive)])
    main()
    with connect(restored) as db:
        assert authenticate(db, "operator", "private-fixture-password")
        assert db.execute("SELECT count(*) FROM packets").fetchone()[0] == 1
