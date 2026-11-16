"""Calibration discussion and operational (self-reported) timing."""

import json
from datetime import datetime
from pathlib import Path

from wikinews_ir.annotation import (
    audit,
    import_packet,
    latest,
    now,
    packet_data,
    require_coordinator,
    transaction,
)


def activate_freeze(db, actor, directory):
    """Activate the exact frozen gold subset, leaving silver-only pairs unassigned."""
    from wikinews_ir.annotation_workflow import ordered
    from wikinews_ir.evaluation.artifacts import file_sha, read_rows, verify_bundle

    require_coordinator(db, actor)
    directory = Path(directory)
    archive = directory / "archive"
    manifest = verify_bundle(archive, "benchmark-freeze")
    packet_manifest = verify_bundle(directory / "packet", "packet")
    if packet_manifest["metadata"].get("freeze_manifest_sha256") != file_sha(archive / "manifest.json"):
        raise ValueError("Pacchetto non collegato al congelamento")
    if (archive / "packet.json").read_bytes() != (directory / "packet/packet.json").read_bytes():
        raise ValueError("Pacchetto diverso dall'archivio congelato")
    plan = json.loads((archive / "plan.json").read_text("utf-8"))
    name = "assignments__" + Path(plan["assignments"]).name
    if name not in manifest["artifacts"]:
        raise ValueError("Assegnazioni non coperte dal manifest")
    rows = read_rows(archive / name)
    for user in {r["user_id"] for r in rows}:
        if not db.execute("SELECT 1 FROM users WHERE id=?", (user,)).fetchone():
            raise ValueError(f"Creare prima l'account {user}")
    packet_id = import_packet(db, directory / "packet")
    wanted = {(r["query_id"], r["document_id"], r["user_id"]) for r in rows}
    with transaction(db):
        existing = {tuple(r) for r in db.execute(
            "SELECT query_id,document_id,user_id FROM assignments WHERE packet_id=?", (packet_id,))}
        if existing:
            if existing != wanted:
                raise RuntimeError("Assegnazioni esistenti diverse dal piano congelato")
            return {"packet_id": packet_id, "assignments": len(existing), "already_active": True}
        for user, qid in sorted({(r["user_id"], r["query_id"]) for r in rows}):
            docs = [r["document_id"] for r in rows if r["user_id"] == user and r["query_id"] == qid]
            for pos, doc in enumerate(ordered(docs, plan["seed"], user)):
                db.execute("INSERT INTO assignments VALUES(?,?,?,?,?)", (packet_id, qid, doc, user, pos))
        audit(db, actor, "frozen_assignments_activated", packet_id=packet_id,
              freeze_manifest_sha256=file_sha(archive / "manifest.json"), assignments=len(wanted))
    return {"packet_id": packet_id, "assignments": len(wanted), "already_active": False}


def discussion(db, actor, packet_id, minutes=None, participants=None, notes=None):
    require_coordinator(db, actor)
    with transaction(db):
        payload = packet_data(db, packet_id)
        if any(t["split"] != "calibration" for t in payload["topics"]):
            raise ValueError("Discussione solo per pacchetti di calibrazione")
        assignments = [dict(r) for r in db.execute(
            "SELECT * FROM assignments WHERE packet_id=?", (packet_id,))]
        if len({a["user_id"] for a in assignments}) != 3:
            raise RuntimeError("Il pilot richiede gli stessi tre validatori")
        expected = {(p["query_id"], p["document_id"]) for p in payload["pairs"]}
        for qid, did in expected:
            members = [a for a in assignments if (a["query_id"], a["document_id"]) == (qid, did)]
            if len(members) != 3:
                raise RuntimeError("Richieste tre assegnazioni per ogni coppia")
            for member in members:
                row = latest(db, (packet_id, qid, did), member["user_id"])
                if not row or row["status"] == "deferred":
                    raise RuntimeError("Fase indipendente non completata")
        db.execute("INSERT OR IGNORE INTO pilot_discussions(packet_id,opened_at,opened_by) "
                   "VALUES(?,?,?)", (packet_id, now(), actor))
        if minutes is not None:
            users = {a["user_id"] for a in assignments}
            if minutes <= 0 or not notes or not notes.strip() or set(participants or []) != users:
                raise ValueError("Verbale, durata positiva e tutti i partecipanti richiesti")
            db.execute("UPDATE pilot_discussions SET minutes=?,participants=?,notes=? "
                       "WHERE packet_id=?", (minutes, json.dumps(sorted(users)), notes, packet_id))
        audit(db, actor, "calibration_discussion", packet_id=packet_id,
              minutes=minutes, participants=participants, notes=notes)
        originals = [dict(latest(db, (packet_id, a["query_id"], a["document_id"]), a["user_id"]))
                     for a in assignments]
        return {"discussion": dict(db.execute("SELECT * FROM pilot_discussions WHERE packet_id=?",
                                             (packet_id,)).fetchone()), "originals": originals,
                "topics": payload["topics"], "documents": payload["documents"]}


def timer(db, actor, timer_id, key, phase, seconds=0, stop=False):
    """Monotonic cumulative checkpoints make retries idempotent. Missing tails stay missing."""
    if phase not in {"reading", "annotation", "review"} or not 0 <= seconds <= 86400:
        raise ValueError("Fase o durata non valida")
    with transaction(db):
        if phase == "review":
            allowed = db.execute("SELECT 1 FROM reviews WHERE packet_id=? AND query_id=? "
                                 "AND document_id=? AND reviewer=? AND state='pending'",
                                 (*key, actor)).fetchone()
        else:
            allowed = db.execute("SELECT 1 FROM assignments WHERE packet_id=? AND query_id=? "
                                 "AND document_id=? AND user_id=?", (*key, actor)).fetchone()
        if not allowed:
            raise PermissionError("Attività non assegnata")
        row = db.execute("SELECT * FROM timing WHERE id=?", (timer_id,)).fetchone()
        if row:
            if (row["user_id"], row["packet_id"], row["query_id"], row["document_id"], row["phase"]) != (
                actor, *key, phase
            ):
                raise ValueError("Identità timer incompatibile")
            if not row["active"]:
                if seconds == row["seconds"] and stop:
                    return dict(row)
                raise RuntimeError("Timer chiuso; avvia una nuova sessione")
            elapsed = (datetime.fromisoformat(now()) - datetime.fromisoformat(row["updated_at"])).total_seconds()
            if seconds < row["seconds"] or seconds - row["seconds"] > elapsed + 5:
                raise ValueError("Durata non monotona o superiore al tempo trascorso")
            db.execute("UPDATE timing SET seconds=?,updated_at=?,active=?,complete=? WHERE id=?",
                       (seconds, now(), int(not stop), int(stop), timer_id))
        else:
            if seconds != 0 or stop:
                raise ValueError("Il timer deve iniziare da zero")
            active = db.execute("SELECT * FROM timing WHERE user_id=? AND active=1", (actor,)).fetchone()
            if active:
                age = (datetime.fromisoformat(now()) - datetime.fromisoformat(active["updated_at"])).total_seconds()
                if age < 45:
                    raise RuntimeError("Un timer è già attivo: mettilo in pausa o attendi 45 secondi")
                db.execute("UPDATE timing SET active=0 WHERE id=?", (active["id"],))
            db.execute("INSERT INTO timing VALUES(?,?,?,?,?,?,0,?,1,0)",
                       (timer_id, actor, *key, phase, now()))
        return dict(db.execute("SELECT * FROM timing WHERE id=?", (timer_id,)).fetchone())
