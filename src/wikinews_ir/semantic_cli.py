"""Build portable semantic collections and publish verified immutable generations."""

import itertools
import json
import math
import os
import uuid
from pathlib import Path

import httpx
from elastic_transport import TransportError
from elasticsearch import ApiError
from filelock import FileLock

from wikinews_ir.ingestion.corpus import canonical, checksum, clean_html, records
from wikinews_ir.retrieval.profiles import digest
from wikinews_ir.semantic import (
    ALIAS,
    DIM,
    call,
    client,
    embed_documents,
    identity,
    prepare,
    tokenizer,
)


def configure(sub):
    ops = sub.add_parser("semantic").add_subparsers(dest="operation", required=True)
    for name in ("preview", "generate", "import", "verify"):
        cmd = ops.add_parser(name)
        cmd.add_argument("--package", type=Path, required=name != "preview")
        if name == "generate":
            cmd.add_argument("--reuse", type=Path, help="Riusa vettori per input identici")
        if name in ("import", "verify"):
            cmd.add_argument(
                "--check-archive",
                action="store_true",
                help="Verifica il corpus del lettore Elasticsearch",
            )
        if name in ("preview", "generate"):
            cmd.add_argument("--corpus", type=Path, required=True)
            cmd.add_argument("--raw", type=Path)
            cmd.add_argument("--selection", type=Path, help="JSONL con document_id del pilota")
            cmd.add_argument("--variant", choices=["natural", "stem"], default="natural")
            cmd.add_argument("--limit", type=int, default=5 if name == "preview" else None)


def write(path, value):
    temp = path.with_suffix(".tmp")
    temp.write_text(canonical(value), encoding="utf-8")
    os.replace(temp, path)


def read(path):
    return json.loads(path.read_bytes())


def articles(path, raw, limit, selection):
    with path.open(encoding="utf-8") as stream:
        items = (json.loads(line) for line in stream)
        if selection:
            ids = {
                json.loads(line)["document_id"]
                for line in selection.read_text("utf-8").splitlines()
            }
            selected = [a for a in items if a["document_id"] in ids]
            if len(selected) != len(ids):
                raise ValueError("Selezione con ID assenti dal corpus")
            selected = selected[:limit]
        else:
            selected = list(itertools.islice(items, limit))
    wanted = {(a["provenance"]["member"], a["provenance"]["line"]): a for a in selected}
    for member, line, record, error in records(raw):
        a = wanted.pop((member, line), None)
        if a is not None:
            if error or (str(record["identifier"]), str(record["version"]["identifier"])) != (
                str(a["document_id"]),
                str(a["revision_id"]),
            ):
                raise ValueError("Revisione sorgente incompatibile")
            yield a, clean_html(record["article_body"]["html"], semantic=True)[0]
        if not wanted:
            return
    raise ValueError("Record sorgente mancanti")


def generate(args, model):
    path = args.corpus / "articles.ndjson"
    manifest = read(args.corpus / "manifest.json")
    corpus_hash = checksum(path)
    if corpus_hash != manifest["artifacts"][path.name]:
        raise ValueError("Checksum corpus non valido")
    raw = args.raw or Path("data/raw") / manifest["input_filename"]
    raw_hash = checksum(raw)
    if raw_hash != manifest["input_sha256"] or not manifest["valid"]:
        raise ValueError("Checksum dump HTML non valido")
    if args.limit is not None and args.limit < 1:
        raise ValueError("Il limite deve essere positivo")
    tok = tokenizer(model)
    source = articles(path, raw, args.limit, args.selection)
    if args.operation == "preview":
        return [
            {"body": a["body"], "prepared": prepare(a, body, tok, args.variant)}
            for a, body in source
        ]
    package = args.package
    spec = {
        "encoder": identity(model),
        "cleaning_version": 3,
        "corpus_sha256": corpus_hash,
        "raw_sha256": raw_hash,
        "selection": checksum(args.selection) if args.selection else None,
        "variant": args.variant,
        "limit": args.limit,
        "snapshot": manifest["snapshot_id"],
    }
    config = package / "config.json"
    if config.exists() and read(config) != spec:
        raise ValueError("Configurazione diversa: scegliere un nuovo pacchetto")
    write(config, spec)
    reuse = read(args.reuse / "manifest.json") if args.reuse else None
    if reuse and reuse["encoder"] != spec["encoder"]:
        raise ValueError("Il pacchetto di riuso usa un altro encoder")
    parts = []
    count = skipped = 0
    for i, batch in enumerate(itertools.batched(source, 16)):
        dest = package / f"batch-{i:06}.json"
        # Each batch is committed atomically with a digest over its contents.
        if dest.exists():
            block = read(dest)
            if digest(block["rows"]) != block["sha256"] or block["config"] != digest(spec):
                raise ValueError(f"Batch danneggiato: {dest}")
            rows = block["rows"]
        else:
            rows = [row for a, body in batch if (row := prepare(a, body, tok, args.variant))]
            prior = {}
            if reuse and i < len(reuse["batches"]):
                part = args.reuse / dest.name
                if checksum(part) != reuse["batches"][i]:
                    raise ValueError("Checksum batch di riuso errato")
                prior = {r["input"]: r["vector"] for r in read(part)["rows"]}
            pending = []
            for row in rows:
                if row["input"] in prior:
                    row["vector"] = prior[row["input"]]
                else:
                    pending.append(row)
            if pending:
                vectors = embed_documents(model, pending, tok)
                for row, vector in zip(pending, vectors, strict=True):
                    row["vector"] = vector
            write(dest, {"rows": rows, "sha256": digest(rows), "config": digest(spec)})
        count += len(rows)
        skipped += len(batch) - len(rows)
        parts.append(checksum(dest))
    if not count or identity(model) != spec["encoder"]:
        raise ValueError("Corpus vuoto o modello cambiato")
    result = {**spec, "count": count, "skipped": skipped, "batches": parts}
    write(package / "manifest.json", result)
    return {k: v for k, v in result.items() if k != "batches"}


def package_rows(path, manifest):
    seen = set()
    for i, expected in enumerate(manifest["batches"]):
        part = path / f"batch-{i:06}.json"
        if checksum(part) != expected:
            raise ValueError(f"Checksum errato: {part}")
        block = read(part)
        rows = block["rows"]
        spec = {k: v for k, v in manifest.items() if k not in ("count", "skipped", "batches")}
        if block["config"] != digest(spec) or digest(rows) != block["sha256"]:
            raise ValueError("Batch incompatibile con il manifest")
        for row in rows:
            key = int(row["document_id"])
            if (
                key in seen
                or len(row["vector"]) != DIM
                or not math.isclose(math.hypot(*row["vector"]), 1, abs_tol=1e-6)
            ):
                raise ValueError("ID duplicato o vettore non valido")
            seen.add(key)
        yield rows
    if len(seen) != manifest["count"] or not seen:
        raise ValueError("Conteggio pacchetto errato")


def publish(args, model, db):
    m = read(args.package / "manifest.json")
    if m["variant"] not in ("natural", "stem") or m["encoder"] != identity(model):
        raise ValueError("Runtime o modello incompatibile")
    if args.check_archive:
        from wikinews_ir.retrieval.engine import RetrievalEngine

        archive = RetrievalEngine()
        try:
            if archive.metadata("E0")["corpus_sha256"] != m["corpus_sha256"]:
                raise ValueError("Il pacchetto usa un corpus diverso dal lettore Elasticsearch")
        finally:
            archive.close()
    alias = ALIAS if m["variant"] == "natural" else ALIAS + "-stem"
    prefix = f"news-{digest(m['encoder'])[:24]}-{m['variant']}-{digest(m)[:16]}-"
    aliases = call(db, "GET", "/aliases")["result"]["aliases"]
    previous = next((r["collection_name"] for r in aliases if r["alias_name"] == alias), None)
    # Retrying a completed import validates the existing immutable generation.
    importing = args.operation == "import" and not (previous and previous.startswith(prefix))
    name = prefix + uuid.uuid4().hex if importing else previous
    if not name or not name.startswith(prefix):
        raise ValueError("Il pacchetto non corrisponde alla collezione attiva")
    base = "/collections/" + name
    if importing:
        call(db, "PUT", base, json={"vectors": {"size": DIM, "distance": "Cosine"}})
    try:
        vectors = call(db, "GET", base)["result"]["config"]["params"]["vectors"]
        if vectors["size"] != DIM or vectors["distance"] != "Cosine":
            raise ValueError("Configurazione vettoriale Qdrant incompatibile")
        for batch in package_rows(args.package, m):
            if not batch:
                continue
            points = [
                {
                    "id": int(row["document_id"]),
                    "vector": row["vector"],
                    "payload": {
                        k: v for k, v in row.items() if k not in ("vector", "input", "tokens")
                    },
                }
                for row in batch
            ]
            if importing:
                call(db, "PUT", base + "/points?wait=true", json={"points": points})
            stored = call(
                db,
                "POST",
                base + "/points",
                json={"ids": [p["id"] for p in points], "with_payload": True},
            )["result"]
            if {p["id"]: p["payload"] for p in stored} != {p["id"]: p["payload"] for p in points}:
                raise ValueError("Identità o metadati dei documenti incompatibili")
        count = call(db, "POST", base + "/points/count", json={"exact": True})["result"]["count"]
        if count != m["count"]:
            raise ValueError("Conteggio Qdrant errato")
    except Exception:
        if importing:
            call(db, "DELETE", base)
        raise
    if importing:
        actions = [{"delete_alias": {"alias_name": alias}}] if previous else []
        actions.append({"create_alias": {"collection_name": name, "alias_name": alias}})
        call(db, "POST", "/collections/aliases", json={"actions": actions})
    return {"alias": alias, "collection": name, "previous": previous, "count": count}


def dispatch(args, parser):
    try:
        with client("ollama") as model:
            if args.operation == "generate":
                args.package.mkdir(parents=True, exist_ok=True)
                with FileLock(str(args.package / ".build.lock"), timeout=0):
                    result = generate(args, model)
            elif args.operation == "preview":
                result = generate(args, model)
            else:
                with client("qdrant") as db:
                    result = publish(args, model, db)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (
        OSError,
        ValueError,
        KeyError,
        RuntimeError,
        TransportError,
        ApiError,
        httpx.HTTPError,
    ) as exc:
        parser.exit(1, f"Ricerca semantica: {exc}\n")
