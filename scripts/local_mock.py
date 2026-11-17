"""Populate a clearly labelled, repeatable UI demo in the local annotation database."""
import copy
import secrets
from pathlib import Path
from tempfile import TemporaryDirectory

from wikinews_ir.annotation import connect, create_user, import_packet, latest, save
from wikinews_ir.annotation_cli import backup, demo_payload
from wikinews_ir.annotation_workflow import activate_block, assign_review, create_block, dashboard
from wikinews_ir.evaluation.artifacts import encoded, write_bundle

ROOT = Path(__file__).resolve().parents[1]


def populate(path, actor="luca"):
    payload = demo_payload()
    template = payload["topics"][0]
    payload["topics"] = []
    payload["pairs"] = []
    for suffix, title, split in [
        ("personali", "MOCK · Energia solare nelle scuole — le tue attività", "calibration"),
        ("revisioni", "MOCK · Energia solare nelle scuole — revisioni", "development"),
        ("bozza", "MOCK · Energia solare nelle scuole — nuove assegnazioni", "development"),
    ]:
        topic = copy.deepcopy(template)
        topic.update(query_id="mock-ui-" + suffix, query=title, split=split,
                     event_family="mock-ui-" + suffix)
        payload["topics"].append(topic)
        payload["pairs"].extend({"query_id": topic["query_id"], "document_id": d["document_id"]} for d in payload["documents"])
    for doc in payload["documents"]:
        doc["title"] = "[MOCK] " + doc["title"]
    with TemporaryDirectory() as temporary:
        bundle = Path(temporary) / "packet"
        write_bundle(bundle, "packet", {"packet.json": encoded(payload)})
        with connect(path) as db:
            if not db.execute("SELECT 1 FROM users WHERE id=? AND coordinator=1", (actor,)).fetchone():
                raise ValueError("Serve l'account coordinatore locale luca.")
            packet = import_packet(db, bundle)
            for user in ["mock-anna", "mock-marco"]:
                if not db.execute("SELECT 1 FROM users WHERE id=?", (user,)).fetchone():
                    create_user(db, user, secrets.token_urlsafe(24))
            for suffix, primary, secondary, active in [
                ("personali", actor, None, True),
                ("revisioni", "mock-anna", "mock-marco", True),
                ("bozza", actor, "mock-anna", False),
            ]:
                query = "mock-ui-" + suffix
                row = db.execute("SELECT id,active FROM blocks WHERE packet_id=? AND query_id=?", (packet, query)).fetchone()
                if not row:
                    result = create_block(db, actor, packet, query, primary, secondary, 4 if secondary else 0, "mock-ui-v1")
                    if active:
                        activate_block(db, actor, result["block"]["id"])

            def submit(user, suffix, number, status, grade, reason):
                key = (packet, "mock-ui-" + suffix, f"demo-{number}")
                if latest(db, key, user):
                    return
                document = payload["documents"][number - 1]
                quote = document["body"].split(".")[0]
                evidence = [{"field": "body", "quote": quote, "start": 0, "end": len(quote)}]
                save(db, user, *key, 0, f"mock-ui-v1:{user}:{suffix}:{number}", status, grade, reason, evidence)
                if user == actor and suffix == "personali" and number == 1:
                    save(db, user, *key, 1, "mock-ui-v1:history", status, grade,
                         reason + " Revisione della motivazione: installazione già completata.", evidence)

            submit(actor, "personali", 1, "judged", 2, "[MOCK] Il testo descrive un impianto installato in una scuola.")
            submit(actor, "personali", 2, "deferred", None, "[MOCK] Bozza salvata: da rileggere prima di assegnare il grado.")
            submit(actor, "personali", 3, "needs_review", None, "[MOCK] Non è chiaro se siano previste installazioni: richiedo una revisione.")
            for number in [1, 2, 3]:
                for user, grade in [("mock-anna", 2 if number == 1 else 0), ("mock-marco", 1 if number < 3 else 0)]:
                    submit(user, "revisioni", number, "judged", grade, f"[MOCK] Valutazione dimostrativa di {user}; confronto con i criteri del topic.")
            key = (packet, "mock-ui-revisioni", "demo-1")
            row = db.execute("SELECT reviewer FROM reviews WHERE packet_id=? AND query_id=? AND document_id=?", key).fetchone()
            if row and not row["reviewer"]:
                assign_review(db, actor, key, actor)
            result = dashboard(db, actor)
            print(f"Pacchetto MOCK pronto: {packet[:8]}; blocchi: {len(result['blocks'])}; revisioni pendenti: {len(result['pending_reviews'])}")
            return packet


if __name__ == "__main__":
    path = ROOT / "data/annotation/annotation.sqlite3"
    from datetime import datetime
    destination = ROOT / "output/local" / ("before-mock-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f") + ".sqlite3")
    destination.parent.mkdir(parents=True, exist_ok=True)
    backup(path, destination)
    populate(path)
