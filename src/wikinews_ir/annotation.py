"""SQLite storage and independent human judgments over immutable M5-A packets."""

import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from wikinews_ir.evaluation.artifacts import file_sha, verify_bundle
from wikinews_ir.evaluation.contracts import Evidence
from wikinews_ir.evaluation.silver import validate_payload


def now():
    return datetime.now(UTC).isoformat()


class Connection(sqlite3.Connection):
    def __exit__(self, *args):
        try:
            return super().__exit__(*args)
        finally:
            self.close()


def connect(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=10, isolation_level=None, factory=Connection)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("PRAGMA journal_mode=WAL")
    version = db.execute("PRAGMA user_version").fetchone()[0]
    if version > 1:
        db.close()
        raise ValueError("Database creato da una versione più recente")
    if version == 0:
        # Upgrade the unversioned prototype without dropping existing rows.
        db.executescript("""
        BEGIN IMMEDIATE;
        CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY, password TEXT NOT NULL,
          coordinator INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS sessions(token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL
          REFERENCES users(id), expires TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS packets(id TEXT PRIMARY KEY, payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS assignments(packet_id TEXT NOT NULL REFERENCES packets(id),
          query_id TEXT NOT NULL, document_id TEXT NOT NULL, user_id TEXT NOT NULL REFERENCES users(id),
          position INTEGER NOT NULL, PRIMARY KEY(packet_id,query_id,document_id,user_id));
        CREATE TABLE IF NOT EXISTS judgments(id INTEGER PRIMARY KEY AUTOINCREMENT,
          packet_id TEXT NOT NULL, query_id TEXT NOT NULL, document_id TEXT NOT NULL,
          user_id TEXT NOT NULL, version INTEGER NOT NULL, status TEXT NOT NULL,
          grade INTEGER, rationale TEXT NOT NULL, evidence TEXT NOT NULL,
          saved_at TEXT NOT NULL, request_id TEXT NOT NULL UNIQUE);
        CREATE UNIQUE INDEX IF NOT EXISTS judgment_version ON judgments
          (packet_id,query_id,document_id,user_id,version);
        CREATE TABLE IF NOT EXISTS session_csrf(token_hash TEXT PRIMARY KEY
          REFERENCES sessions(token_hash) ON DELETE CASCADE, csrf TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS login_attempts(key TEXT PRIMARY KEY, attempts INTEGER NOT NULL,
          reset_at REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS packet_manifests(packet_id TEXT PRIMARY KEY REFERENCES packets(id),
          manifest TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS blocks(id TEXT PRIMARY KEY, packet_id TEXT NOT NULL
          REFERENCES packets(id), query_id TEXT NOT NULL, primary_user TEXT NOT NULL REFERENCES users(id),
          secondary_user TEXT REFERENCES users(id), overlap INTEGER NOT NULL, seed TEXT NOT NULL,
          active INTEGER NOT NULL DEFAULT 0, created_by TEXT NOT NULL REFERENCES users(id));
        CREATE UNIQUE INDEX IF NOT EXISTS active_topic ON blocks(packet_id,query_id) WHERE active=1;
        CREATE TABLE IF NOT EXISTS decisions(id INTEGER PRIMARY KEY AUTOINCREMENT,
          packet_id TEXT NOT NULL, query_id TEXT NOT NULL, document_id TEXT NOT NULL,
          method TEXT NOT NULL, actor TEXT, status TEXT NOT NULL, grade INTEGER,
          rationale TEXT NOT NULL, evidence TEXT NOT NULL, origins TEXT NOT NULL,
          created_at TEXT NOT NULL, current INTEGER NOT NULL DEFAULT 1);
        CREATE UNIQUE INDEX IF NOT EXISTS current_decision ON decisions
          (packet_id,query_id,document_id) WHERE current=1;
        CREATE TABLE IF NOT EXISTS reviews(packet_id TEXT NOT NULL, query_id TEXT NOT NULL,
          document_id TEXT NOT NULL, reviewer TEXT REFERENCES users(id), basis TEXT NOT NULL,
          state TEXT NOT NULL, PRIMARY KEY(packet_id,query_id,document_id));
        CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY AUTOINCREMENT,
          actor TEXT, action TEXT NOT NULL, details TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS requests(id TEXT PRIMARY KEY, actor TEXT NOT NULL,
          fingerprint TEXT NOT NULL, result TEXT NOT NULL);
        PRAGMA user_version=1;
        COMMIT;
        """)
    return db


@contextmanager
def transaction(db):
    db.execute("BEGIN IMMEDIATE")
    try:
        yield
        db.execute("COMMIT")
    except BaseException:
        db.execute("ROLLBACK")
        raise


def audit(db, actor, action, **details):
    db.execute("INSERT INTO audit(actor,action,details,created_at) VALUES(?,?,?,?)",
               (actor, action, json.dumps(details, ensure_ascii=False), now()))


def password_hash(password):
    if len(password) < 10 or len(password) > 1024:
        raise ValueError("La password deve contenere da 10 a 1024 caratteri")
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1)
    return (salt + digest).hex()


def create_user(db, user_id, password, coordinator=False):
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", user_id):
        raise ValueError("Identificativo utente non valido")
    with transaction(db):
        db.execute("INSERT INTO users VALUES(?,?,?)",
                   (user_id, password_hash(password), int(coordinator)))
        audit(db, user_id, "user_created", coordinator=coordinator)


def reset_password(db, user_id, password):
    hashed = password_hash(password)
    with transaction(db):
        if not db.execute("UPDATE users SET password=? WHERE id=?", (hashed, user_id)).rowcount:
            raise ValueError("Utente inesistente")
        db.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))
        audit(db, user_id, "password_reset")


def authenticate(db, user_id, password):
    row = db.execute("SELECT password FROM users WHERE id=?", (user_id,)).fetchone()
    raw = bytes.fromhex(row[0]) if row else bytes(80)
    digest = hashlib.scrypt(password.encode(), salt=raw[:16], n=16384, r=8, p=1)
    return hmac.compare_digest(raw[16:], digest) and row is not None


def require_coordinator(db, user_id):
    row = db.execute("SELECT coordinator FROM users WHERE id=?", (user_id,)).fetchone()
    if not row or not row[0]:
        raise PermissionError("Ruolo di coordinatore richiesto")


def packet_data(db, packet_id):
    row = db.execute("SELECT payload FROM packets WHERE id=?", (packet_id,)).fetchone()
    if row is None:
        raise ValueError("Pacchetto inesistente")
    return json.loads(row[0])


def pair_data(db, packet_id, query_id, document_id):
    payload = packet_data(db, packet_id)
    if {"query_id": query_id, "document_id": document_id} not in payload["pairs"]:
        raise ValueError("Coppia fuori pacchetto")
    topic = next(t for t in payload["topics"] if t["query_id"] == query_id)
    document = next(d for d in payload["documents"] if d["document_id"] == document_id)
    return payload, topic, document


def import_packet(db, directory):
    directory = Path(directory)
    manifest = verify_bundle(directory, "packet")
    if "packet.json" not in manifest["artifacts"]:
        raise ValueError("packet.json non coperto dal manifest")
    payload = validate_payload(json.loads((directory / "packet.json").read_text("utf-8")))
    if payload["protocol"]["status"] != "frozen" and any(
        topic["split"] == "test" for topic in payload["topics"]
    ):
        raise ValueError("Il test richiede un protocollo congelato")
    packet_id = file_sha(directory / "packet.json")
    with transaction(db):
        db.execute("INSERT OR IGNORE INTO packets VALUES(?,?)", (packet_id, json.dumps(payload)))
        db.execute("INSERT OR IGNORE INTO packet_manifests VALUES(?,?)",
                   (packet_id, json.dumps(manifest)))
        audit(db, None, "packet_imported", packet_id=packet_id)
    return packet_id


def latest(db, key, user_id):
    row = db.execute("SELECT * FROM judgments WHERE packet_id=? AND query_id=? AND document_id=? "
                     "AND user_id=? ORDER BY version DESC LIMIT 1", (*key, user_id)).fetchone()
    return dict(row) if row else None


def public_judgment(row):
    if not row:
        return None
    return {**{k: row[k] for k in ("id", "version", "status", "grade", "rationale", "saved_at")},
            "evidence": json.loads(row["evidence"])}


def tasks(db, user_id):
    rows = db.execute("SELECT * FROM assignments WHERE user_id=? "
                      "ORDER BY packet_id,query_id,position,document_id", (user_id,)).fetchall()
    result, packets = [], {}
    for row in rows:
        key = tuple(row[k] for k in ("packet_id", "query_id", "document_id"))
        if key[0] not in packets:
            payload = packet_data(db, key[0])
            packets[key[0]] = ({t["query_id"]: t for t in payload["topics"]},
                               {d["document_id"]: d for d in payload["documents"]})
        topics, documents = packets[key[0]]
        topic, document = topics[key[1]], documents[key[2]]
        result.append({"packet_id": key[0], "topic": topic, "document": document,
                       "own_judgment": public_judgment(latest(db, key, user_id))})
    return result


def own_history(db, user_id, key):
    if not db.execute("SELECT 1 FROM assignments WHERE packet_id=? AND query_id=? "
                      "AND document_id=? AND user_id=?", (*key, user_id)).fetchone():
        raise PermissionError("Attività non assegnata")
    return [public_judgment(dict(r)) for r in db.execute(
        "SELECT * FROM judgments WHERE packet_id=? AND query_id=? AND document_id=? "
        "AND user_id=? ORDER BY version DESC", (*key, user_id))]


def validate_decision(body, status, grade, rationale, evidence):
    if status not in {"judged", "needs_review", "deferred"}:
        raise ValueError("Stato non valido")
    normalized = [Evidence.model_validate(item).model_dump() for item in evidence]
    for item in normalized:
        start, end = item["start"], item["end"]
        if (start is None or end is None or not 0 <= start < end <= len(body)
                or body[start:end] != item["quote"]):
            raise ValueError("Citazione non valida")
    if status == "judged" and (
        type(grade) is not int or grade not in (0, 1, 2) or not normalized or not rationale.strip()
    ):
        raise ValueError("Grado, evidenza e motivazione richiesti")
    if status != "judged" and grade is not None:
        raise ValueError("Grado non ammesso")
    if status == "needs_review" and not rationale.strip():
        raise ValueError("Motivazione dell'astensione richiesta")
    return normalized


def replay(db, request_id, actor, payload):
    fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    row = db.execute("SELECT * FROM requests WHERE id=?", (request_id,)).fetchone()
    if row and (row["actor"] != actor or row["fingerprint"] != fingerprint):
        raise ValueError("Chiave di idempotenza già utilizzata")
    return fingerprint, json.loads(row["result"]) if row else None


def save(db, user_id, packet_id, query_id, document_id, expected_version, request_id,
         status, grade, rationale, evidence):
    from wikinews_ir.annotation_workflow import consolidate

    key = packet_id, query_id, document_id
    with transaction(db):
        if not db.execute("SELECT 1 FROM assignments WHERE packet_id=? AND query_id=? "
                          "AND document_id=? AND user_id=?", (*key, user_id)).fetchone():
            raise PermissionError("Attività non assegnata")
        _, _, document = pair_data(db, *key)
        evidence = validate_decision(document["body"], status, grade, rationale, evidence)
        fingerprint, previous = replay(db, request_id, user_id, {
            "key": key, "expected_version": expected_version, "status": status,
            "grade": grade, "rationale": rationale, "evidence": evidence})
        if previous is not None:
            return previous
        current = latest(db, key, user_id)
        version = current["version"] if current else 0
        if version != expected_version:
            raise RuntimeError("Versione superata: ricarica l'attività prima di modificare")
        db.execute("INSERT INTO judgments(packet_id,query_id,document_id,user_id,version,status,"
                   "grade,rationale,evidence,saved_at,request_id) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                   (*key, user_id, version + 1, status, grade, rationale,
                    json.dumps(evidence), now(), request_id))
        consolidate(db, key)
        audit(db, user_id, "judgment_saved", packet_id=packet_id, query_id=query_id,
              document_id=document_id, version=version + 1)
        db.execute("INSERT INTO requests VALUES(?,?,?,?)",
                   (request_id, user_id, fingerprint, json.dumps(version + 1)))
        return version + 1


def database_path():
    return os.environ.get("ANNOTATION_DB", "data/annotation/annotation.sqlite3")
