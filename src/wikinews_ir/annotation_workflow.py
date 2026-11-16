"""Assignments, consolidation and independent adjudication."""

import hashlib
import json
from collections import Counter
from uuid import uuid4

from wikinews_ir.annotation import (
    audit,
    latest,
    now,
    packet_data,
    pair_data,
    public_judgment,
    replay,
    require_coordinator,
    transaction,
    validate_decision,
)


def ordered(values, seed, salt):
    return sorted(values, key=lambda value: hashlib.sha256(
        json.dumps([seed, salt, value], ensure_ascii=False).encode()).hexdigest())


def block_preview(db, block):
    payload = packet_data(db, block["packet_id"])
    documents = sorted(p["document_id"] for p in payload["pairs"]
                       if p["query_id"] == block["query_id"])
    if not documents:
        raise ValueError("Topic senza coppie nel pacchetto")
    if not 0 <= block["overlap"] <= len(documents):
        raise ValueError("Sovrapposizione fuori intervallo")
    if block["overlap"] and not block["secondary_user"]:
        raise ValueError("Secondo annotatore richiesto")
    if block["primary_user"] == block["secondary_user"]:
        raise ValueError("Gli annotatori devono essere distinti")
    for user in (block["primary_user"], block["secondary_user"]):
        if user and not db.execute("SELECT 1 FROM users WHERE id=?", (user,)).fetchone():
            raise ValueError("Utente inesistente")
    overlap = ordered(documents, block["seed"], "overlap")[:block["overlap"]]
    assignments = []
    for user, docs in ((block["primary_user"], documents), (block["secondary_user"], overlap)):
        if user:
            assignments.extend({"user_id": user, "document_id": doc, "position": pos}
                               for pos, doc in enumerate(ordered(docs, block["seed"], user)))
    return {"block": dict(block), "distinct_pairs": len(documents),
            "double_pairs": len(overlap), "assignments": assignments}


def create_block(db, actor, packet_id, query_id, primary_user, secondary_user, overlap, seed):
    require_coordinator(db, actor)
    block = dict(id=uuid4().hex, packet_id=packet_id, query_id=query_id,
                 primary_user=primary_user, secondary_user=secondary_user, overlap=overlap,
                 seed=seed, active=0, created_by=actor)
    preview = block_preview(db, block)
    with transaction(db):
        db.execute("INSERT INTO blocks VALUES(?,?,?,?,?,?,?,?,?)", tuple(block.values()))
        audit(db, actor, "block_prepared", packet_id=packet_id, block_id=block["id"])
    return preview


def activate_block(db, actor, block_id):
    require_coordinator(db, actor)
    with transaction(db):
        row = db.execute("SELECT * FROM blocks WHERE id=?", (block_id,)).fetchone()
        if not row:
            raise ValueError("Blocco inesistente")
        block = dict(row)
        if block["active"]:
            return block_preview(db, block)
        if db.execute("SELECT 1 FROM assignments WHERE packet_id=? AND query_id=?",
                      (block["packet_id"], block["query_id"])).fetchone():
            raise RuntimeError("Topic già assegnato: le assegnazioni attive sono congelate")
        preview = block_preview(db, block)
        for item in preview["assignments"]:
            db.execute("INSERT INTO assignments VALUES(?,?,?,?,?)", (
                block["packet_id"], block["query_id"], item["document_id"],
                item["user_id"], item["position"]))
        db.execute("UPDATE blocks SET active=1 WHERE id=?", (block_id,))
        audit(db, actor, "block_activated", packet_id=block["packet_id"], block_id=block_id)
        preview["block"]["active"] = 1
        return preview


def originals(db, key):
    users = [r[0] for r in db.execute("SELECT user_id FROM assignments WHERE packet_id=? "
                                    "AND query_id=? AND document_id=? ORDER BY user_id", key)]
    return [latest(db, key, user) for user in users]


def basis_for(rows):
    return json.dumps([row["id"] for row in rows])


def add_decision(db, key, method, actor, status, grade, rationale, evidence, origins):
    db.execute("UPDATE decisions SET current=0 WHERE packet_id=? AND query_id=? "
               "AND document_id=? AND current=1", key)
    result = db.execute("INSERT INTO decisions(packet_id,query_id,document_id,method,actor,status,"
                        "grade,rationale,evidence,origins,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                        (*key, method, actor, status, grade, rationale, json.dumps(evidence),
                         origins, now()))
    return result.lastrowid


def consolidate(db, key):
    """Caller owns the transaction, so a changed original never leaves a stale final."""
    rows = originals(db, key)
    db.execute("UPDATE decisions SET current=0 WHERE packet_id=? AND query_id=? "
               "AND document_id=? AND current=1", key)
    if not rows or any(not r or r["status"] == "deferred" for r in rows):
        db.execute("UPDATE reviews SET state='waiting',basis='' WHERE packet_id=? "
                   "AND query_id=? AND document_id=?", key)
        return
    basis = basis_for(rows)
    if all(r["status"] == "judged" for r in rows) and len({r["grade"] for r in rows}) == 1:
        first = rows[0]
        add_decision(db, key, "automatic", None, "judged", first["grade"], first["rationale"],
                     json.loads(first["evidence"]), basis)
        db.execute("UPDATE reviews SET state='closed',basis=? WHERE packet_id=? "
                   "AND query_id=? AND document_id=?", (basis, *key))
    else:
        db.execute("INSERT INTO reviews VALUES(?,?,?,NULL,?,'pending') "
                   "ON CONFLICT(packet_id,query_id,document_id) DO UPDATE "
                   "SET basis=excluded.basis,state='pending'", (*key, basis))


def assign_review(db, actor, key, reviewer):
    require_coordinator(db, actor)
    with transaction(db):
        row = db.execute("SELECT * FROM reviews WHERE packet_id=? AND query_id=? "
                         "AND document_id=? AND state='pending'", key).fetchone()
        if not row:
            raise RuntimeError("Revisione non disponibile")
        if not db.execute("SELECT 1 FROM users WHERE id=?", (reviewer,)).fetchone():
            raise ValueError("Revisore inesistente")
        if db.execute("SELECT 1 FROM assignments WHERE packet_id=? AND query_id=? "
                      "AND document_id=? AND user_id=?", (*key, reviewer)).fetchone():
            raise PermissionError("Il revisore deve essere indipendente dagli annotatori")
        db.execute("UPDATE reviews SET reviewer=? WHERE packet_id=? AND query_id=? AND document_id=?",
                   (reviewer, *key))
        audit(db, actor, "review_assigned", packet_id=key[0], query_id=key[1],
              document_id=key[2], reviewer=reviewer)


def review_tasks(db, user_id):
    result = []
    for row in db.execute("SELECT * FROM reviews WHERE reviewer=? AND state='pending' "
                          "ORDER BY packet_id,query_id,document_id", (user_id,)):
        key = row["packet_id"], row["query_id"], row["document_id"]
        _, topic, document = pair_data(db, *key)
        result.append({"packet_id": key[0], "topic": topic, "document": document,
                       "basis": row["basis"], "originals": [
                           {**public_judgment(r), "annotator_id": r["user_id"]}
                           for r in originals(db, key)]})
    return result


def adjudicate(db, actor, key, basis, request_id, status, grade, rationale, evidence):
    with transaction(db):
        row = db.execute("SELECT * FROM reviews WHERE packet_id=? AND query_id=? AND document_id=?",
                         key).fetchone()
        if not row or row["reviewer"] != actor:
            raise PermissionError("Revisione non assegnata")
        if status == "deferred":
            raise ValueError("Una decisione finale richiede grado o astensione")
        _, _, document = pair_data(db, *key)
        evidence = validate_decision(document["body"], status, grade, rationale, evidence)
        fingerprint, previous = replay(db, request_id, actor, dict(
            key=key, basis=basis, status=status, grade=grade, rationale=rationale, evidence=evidence))
        if previous is not None:
            return previous
        if row["state"] != "pending" or row["basis"] != basis:
            raise RuntimeError("Giudizi modificati: ricarica la revisione")
        decision_id = add_decision(db, key, "adjudication", actor, status, grade,
                                   rationale, evidence, basis)
        db.execute("UPDATE reviews SET state='closed' WHERE packet_id=? AND query_id=? "
                   "AND document_id=?", key)
        db.execute("INSERT INTO requests VALUES(?,?,?,?)",
                   (request_id, actor, fingerprint, json.dumps(decision_id)))
        audit(db, actor, "adjudicated", packet_id=key[0], query_id=key[1], document_id=key[2],
              decision_id=decision_id)
        return decision_id


def dashboard(db, actor):
    require_coordinator(db, actor)
    packets = []
    for row in db.execute("SELECT id,payload FROM packets ORDER BY id"):
        data = json.loads(row["payload"])
        packets.append({"id": row["id"], "topics": [
            {"query_id": t["query_id"], "query": t["query"], "split": t["split"],
             "pairs": sum(p["query_id"] == t["query_id"] for p in data["pairs"])}
            for t in data["topics"]]})
    users = [dict(r) for r in db.execute("SELECT id,coordinator FROM users ORDER BY id")]
    progress = []
    for user in users:
        counts = Counter()
        for row in db.execute("SELECT packet_id,query_id,document_id FROM assignments WHERE user_id=?",
                              (user["id"],)):
            judgment = latest(db, tuple(row), user["id"])
            counts[judgment["status"] if judgment else "unstarted"] += 1
        progress.append({"user_id": user["id"], "total": sum(counts.values()), **counts})
    pending = []
    for row in db.execute("SELECT * FROM reviews WHERE state='pending'"):
        key = row["packet_id"], row["query_id"], row["document_id"]
        assigned = {r[0] for r in db.execute("SELECT user_id FROM assignments WHERE packet_id=? "
                                           "AND query_id=? AND document_id=?", key)}
        pending.append({"packet_id": key[0], "query_id": key[1], "document_id": key[2],
                        "reviewer": row["reviewer"],
                        "eligible": [u["id"] for u in users if u["id"] not in assigned]})
    return {"packets": packets, "users": users, "progress": progress, "pending_reviews": pending,
            "blocks": [dict(r) for r in db.execute("SELECT * FROM blocks ORDER BY rowid")],
            "finalized": db.execute("SELECT count(*) FROM decisions WHERE current=1").fetchone()[0]}
