"""Auditable split-specific exports compatible with the M5-A gold exporter."""

import json
import tempfile
from pathlib import Path

from wikinews_ir.annotation import audit, packet_data, require_coordinator, transaction
from wikinews_ir.evaluation.artifacts import encoded, jsonl, write_bundle
from wikinews_ir.evaluation.contracts import Judgment
from wikinews_ir.evaluation.silver import export_qrels


def judgment_record(row, document, protocol, final=False):
    result = {
        "judgment_id": f"{'final' if final else 'human'}-{row['id']}",
        "query_id": row["query_id"], "document_id": row["document_id"],
        "revision_id": document["revision_id"], "body_sha256": document["body_sha256"],
        "protocol_version": protocol["version"], "source": "human",
        # An explicit machine identifier preserves the existing M5-A contract;
        # decision_provenance.json distinguishes it from a human reviewer.
        "annotator_id": (row["actor"] or "system:auto-consolidation") if final else row["user_id"],
        "judged_at": row["created_at"] if final else row["saved_at"],
        "status": row["status"], "grade": row["grade"], "rationale": row["rationale"],
        "evidence": json.loads(row["evidence"]),
        "ambiguity_reason": row["rationale"] if row["status"] == "needs_review" else None,
        "final": final,
        "origin_judgment_ids": [f"human-{i}" for i in json.loads(row["origins"])] if final else [],
    }
    return Judgment.model_validate(result).model_dump()


def export_snapshot(db, actor, packet_id, split, release_test=False):
    require_coordinator(db, actor)
    if split not in {"calibration", "development", "test"}:
        raise ValueError("Split non valido")
    if split == "test" and not release_test:
        raise PermissionError("Export test richiede rilascio esplicito")
    with transaction(db):
        payload = packet_data(db, packet_id)
        source = db.execute("SELECT manifest FROM packet_manifests WHERE packet_id=?",
                            (packet_id,)).fetchone()
        topics = [t for t in payload["topics"] if t["split"] == split]
        ids = {t["query_id"] for t in topics}
        pairs = [p for p in payload["pairs"] if p["query_id"] in ids]
        if not pairs:
            raise ValueError("Nessuna coppia per lo split richiesto")
        document_ids = {p["document_id"] for p in pairs}
        documents = {d["document_id"]: d for d in payload["documents"]
                     if d["document_id"] in document_ids}
        packet = {**payload, "topics": topics, "pairs": pairs, "documents": list(documents.values())}
        finals = [dict(r) for r in db.execute(
            "SELECT * FROM decisions WHERE packet_id=? AND current=1 ORDER BY query_id,document_id",
            (packet_id,)) if r["query_id"] in ids]
        rows, provenance = [], []
        for final in finals:
            document = documents[final["document_id"]]
            for origin_id in json.loads(final["origins"]):
                origin = db.execute("SELECT * FROM judgments WHERE id=?", (origin_id,)).fetchone()
                rows.append(judgment_record(dict(origin), document, payload["protocol"]))
            rows.append(judgment_record(final, document, payload["protocol"], final=True))
            provenance.append({"judgment_id": f"final-{final['id']}", "method": final["method"],
                               "reviewer": final["actor"]})
        history = [dict(r) for r in db.execute("SELECT * FROM judgments WHERE packet_id=? ORDER BY id",
                                              (packet_id,)) if r["query_id"] in ids]
        decisions = [dict(r) for r in db.execute("SELECT * FROM decisions WHERE packet_id=? ORDER BY id",
                                                (packet_id,)) if r["query_id"] in ids]
        assignments = [dict(r) for r in db.execute("SELECT * FROM assignments WHERE packet_id=?",
                                                  (packet_id,)) if r["query_id"] in ids]
        audit(db, actor, "gold_export", packet_id=packet_id, split=split,
              release_test=release_test, finalized=len(finals))
        pending = len({(r["query_id"], r["document_id"]) for r in history}
                      - {(r["query_id"], r["document_id"]) for r in finals})
        return {"packet": packet, "judgments": rows, "history": history,
                "source_manifest": json.loads(source[0]) if source else None,
                "decisions": decisions, "assignments": assignments, "provenance": provenance,
                "metadata": {"packet_id": packet_id, "split": split, "exported_by": actor,
                             "release_test": release_test, "finalized": len(finals),
                             "pending": pending, "unjudged": len(pairs) - len(finals)}}


def write_export(snapshot, output):
    """Use the existing exporter as the final validator, then publish atomically."""
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        write_bundle(root / "packet", "packet", {"packet.json": encoded(snapshot["packet"])})
        (root / "judgments.jsonl").write_text(
            jsonl(snapshot["judgments"]), encoding="utf-8", newline="\n")
        export_qrels(root / "packet", root / "judgments.jsonl", root / "qrels", "gold")
        files = {
            "packet.json": encoded(snapshot["packet"]),
            "source_manifest.json": encoded(snapshot["source_manifest"]),
            "judgments.jsonl": jsonl(snapshot["judgments"]),
            "history.jsonl": jsonl(snapshot["history"]),
            "decisions.jsonl": jsonl(snapshot["decisions"]),
            "assignments.jsonl": jsonl(snapshot["assignments"]),
            "decision_provenance.json": encoded(snapshot["provenance"]),
            "qrels_gold.tsv": (root / "qrels" / "qrels_gold.tsv").read_text("utf-8"),
            "qrels_manifest.json": (root / "qrels" / "manifest.json").read_text("utf-8"),
        }
        return write_bundle(output, "annotation-gold-export", files, snapshot["metadata"])
