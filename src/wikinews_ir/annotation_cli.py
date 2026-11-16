"""Local administration, demo fixtures and SQLite backup/restore."""

import getpass
import json
import os
import sqlite3
from contextlib import closing
from pathlib import Path

from wikinews_ir.annotation import (
    connect,
    create_user,
    database_path,
    import_packet,
    reset_password,
)
from wikinews_ir.evaluation.artifacts import encoded, sha, write_bundle
from wikinews_ir.evaluation.contracts import Protocol


def demo_payload():
    """Synthetic data only, also used by the independent browser test suite."""
    topic = {
        "query_id": "demo-energia", "query": "energia solare nelle scuole",
        "information_need": "Trovare notizie su impianti solari installati nelle scuole italiane.",
        "narrative": "Sono pertinenti interventi realizzati o in corso; distinguere annunci generici.",
        "relevance_criteria": {"0": "Nessun intervento solare in scuole italiane.",
                               "1": "Tema collegato, ma intervento o sede non chiaramente descritti.",
                               "2": "Intervento solare in una scuola italiana descritto direttamente."},
        "inclusion_criteria": ["Scuole in Italia", "Impianti fotovoltaici o solari termici"],
        "exclusion_criteria": ["Solo proposte generiche", "Impianti non scolastici"],
        "type": "multi-constraint", "theme": "ambiente", "temporal_constraints": {},
        "event_family": "demo-energia", "split": "calibration", "variants": [],
        "ambiguity_notes": [], "selection_rationale": "Fixture sintetica, non benchmark reale.",
    }
    texts = [
        ("Pannelli solari nella scuola di Bologna", "La scuola di Bologna inaugura un impianto "
         "fotovoltaico. ☀️ 📚 Gli studenti seguiranno la produzione di energia durante le lezioni."),
        ("Un nuovo parco cittadino", "Il Comune apre un parco pubblico. Il progetto comprende "
         "alberi e percorsi pedonali, senza interventi negli edifici scolastici."),
        ("Energia pulita: un progetto per gli studenti", "L'associazione propone incontri nelle "
         "scuole sull'energia solare. Non è stata annunciata l'installazione di impianti."),
        ("Il liceo produce energia", "Nel liceo di Torino sono entrati in funzione i pannelli "
         "solari sul tetto. L'impianto fornisce energia alle aule e ai laboratori."),
    ]
    documents = [{"document_id": f"demo-{i}", "revision_id": "fixture-1", "title": title,
                  "body": body, "body_sha256": sha(body), "publication_date": None,
                  "publication_date_status": "missing", "publication_date_evidence": []}
                 for i, (title, body) in enumerate(texts, 1)]
    return {"protocol": Protocol(version="m5b-fixture-1").model_dump(), "topics": [topic],
            "documents": documents, "pairs": [{"query_id": topic["query_id"],
            "document_id": doc["document_id"]} for doc in documents]}


def configure(sub):
    parser = sub.add_parser("annotation", help="Account, pacchetti e archivio di annotazione")
    parser.add_argument("--db", type=Path, default=Path(database_path()))
    commands = parser.add_subparsers(dest="annotation_command", required=True)
    commands.add_parser("init")
    command = commands.add_parser("activate-freeze")
    command.add_argument("--freeze", required=True, type=Path)
    command.add_argument("--actor", required=True)
    for name in ("create-user", "reset-password"):
        command = commands.add_parser(name)
        command.add_argument("user_id")
        command.add_argument("--password-env", help="Nome variabile ambiente; altrimenti prompt sicuro")
        if name == "create-user":
            command.add_argument("--coordinator", action="store_true")
    command = commands.add_parser("import")
    command.add_argument("--packet", required=True, type=Path)
    command = commands.add_parser("demo-packet")
    command.add_argument("--output", required=True, type=Path)
    for name in ("backup", "restore"):
        command = commands.add_parser(name)
        command.add_argument("--output" if name == "backup" else "--input", required=True, type=Path)


def backup(source, destination):
    source, destination = Path(source), Path(destination)
    if not source.is_file():
        raise ValueError("Database sorgente inesistente")
    if destination.exists():
        raise ValueError("La destinazione esiste già")
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation prevents accidental overwrite; SQLite's backup API includes WAL data.
    with destination.open("xb"):
        pass
    try:
        with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)) as original:
            with closing(sqlite3.connect(destination)) as target:
                original.backup(target)
                if target.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise ValueError("Backup non integro")
    except BaseException:
        destination.unlink(missing_ok=True)
        raise
    return {"path": str(destination), "integrity": "ok"}


def dispatch(args):
    command = args.annotation_command
    if command == "demo-packet":
        return write_bundle(args.output, "packet", {"packet.json": encoded(demo_payload())},
                            {"fixture": True, "purpose": "M5-B local validation"})
    if command == "backup":
        return backup(args.db.resolve(), args.output.resolve())
    if command == "restore":
        source = args.input.resolve()
        if not source.is_file():
            raise ValueError("Backup inesistente")
        with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)) as check:
            if check.execute("PRAGMA user_version").fetchone()[0] not in (1, 2):
                raise ValueError("Versione del backup incompatibile")
        return backup(source, args.db.resolve())
    with connect(args.db) as db:
        if command == "activate-freeze":
            from wikinews_ir.pilot import activate_freeze
            return activate_freeze(db, args.actor, args.freeze)
        if command == "init":
            return {"database": str(args.db), "schema_version": 2}
        if command in {"create-user", "reset-password"}:
            password = (os.environ[args.password_env] if args.password_env
                        else getpass.getpass("Password (minimo 10 caratteri): "))
            if command == "create-user":
                create_user(db, args.user_id, password, args.coordinator)
            else:
                reset_password(db, args.user_id, password)
            return {"user_id": args.user_id, "operation": command}
        if command == "import":
            return {"packet_id": import_packet(db, args.packet)}
    raise ValueError("Comando sconosciuto")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    configure(parser.add_subparsers(dest="command", required=True))
    print(json.dumps(dispatch(parser.parse_args()), ensure_ascii=False, indent=2))
