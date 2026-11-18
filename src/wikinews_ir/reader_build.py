"""Build or enrich the read-only NewsFinder reader catalog."""
import argparse
import json
import os
import sqlite3
import tempfile
from collections import defaultdict
from contextlib import closing
from pathlib import Path

import httpx
from lxml.etree import ParserError

from wikinews_ir.adapters.images import credit as credit
from wikinews_ir.adapters.images import fetch_images
from wikinews_ir.adapters.mediawiki import MediaWiki
from wikinews_ir.archive import classify
from wikinews_ir.ingestion.corpus import checksum, records
from wikinews_ir.ingestion.indexer import validate_corpus
from wikinews_ir.reader import DEFAULT_PATH, extract, key


def revisions(dump, docs):
    for _, _, row, error in records(dump):
        if error:
            continue
        ident = str(row["identifier"])
        if ident in docs and docs[ident]["revision_id"] == str(row["version"]["identifier"]):
            yield ident, row


def build(db, corpus, dump, pilot):
    identity = validate_corpus(corpus)
    manifest = json.loads((corpus / "manifest.json").read_bytes())
    if checksum(dump) != manifest["input_sha256"]:
        raise ValueError("Dump diverso da quello del corpus")
    with (corpus / "articles.ndjson").open(encoding="utf8") as stream:
        docs = {d["document_id"]: d for d in map(json.loads, stream)}
    titles = {key(d["title"]): i for i, d in docs.items()}
    groups = defaultdict(list)
    for ident, row in revisions(dump, docs):
        for alias in row.get("redirects", []):
            if isinstance(alias, dict) and alias.get("name"):
                titles.setdefault(key(alias["name"]), ident)
        if pilot:
            markup = row["article_body"]["html"].lower()
            feature = (int(ident) % 5)
            patterns = ("<figure", "wikitable", "<ol", "articoli correlati", "<p")
            if patterns[feature] not in markup:
                feature = 5
            groups[classify(docs[ident]["categories"])[0], feature].append(ident)
    if pilot:
        chosen = []
        for values in groups.values():
            values.sort(key=int, reverse=True)
        while len(chosen) < min(100, len(docs)):
            for values in groups.values():
                if values and len(chosen) < 100:
                    chosen.append(values.pop())
        docs = {i: docs[i] for i in chosen}
    db.executescript("""
        CREATE TABLE manifest(checksum TEXT PRIMARY KEY);
        CREATE TABLE pages(id TEXT PRIMARY KEY, revision TEXT, file TEXT, payload TEXT);
        CREATE TABLE media(name TEXT PRIMARY KEY, data TEXT);
    """)
    db.execute("INSERT INTO manifest VALUES (?)", (identity["corpus_sha256"],))
    for ident, row in revisions(dump, docs):
        try:
            page = extract(row["article_body"]["html"], row["url"], titles)
        except (ParserError, RecursionError, ValueError):
            page = None
        name = page["file"] if page else None
        db.execute("INSERT OR IGNORE INTO pages VALUES (?,?,?,?)", (ident, docs[ident]["revision_id"],
                   name, json.dumps(page, ensure_ascii=False) if page else None))
    if db.execute("SELECT count(*) FROM pages").fetchone()[0] != len(docs):
        raise ValueError("Revisioni mancanti nel catalogo")


def enrich(db, user_agent):
    db.execute("""CREATE TABLE IF NOT EXISTS media_checks
                  (name TEXT PRIMARY KEY, status TEXT, checked INTEGER)""")
    names = [r[0] for r in db.execute("""SELECT DISTINCT p.file FROM pages p
        LEFT JOIN media m ON m.name=p.file LEFT JOIN media_checks c ON c.name=p.file
        WHERE p.file IS NOT NULL AND m.data IS NULL AND
        (c.checked IS NULL OR c.status NOT IN ('credited','no_credit') OR c.checked <= unixepoch()-604800)
        ORDER BY p.file""")]
    api = MediaWiki(user_agent)
    try:
        for offset in range(0, len(names), 25):
            batch = names[offset:offset+25]
            try:
                images = fetch_images(api, batch, 800)
            except (httpx.HTTPError, ValueError):
                db.executemany("INSERT OR REPLACE INTO media_checks VALUES (?, 'temporary', unixepoch())",
                               [(name,) for name in batch])
                db.commit()
                raise
            for name, image in images.items():
                db.execute("INSERT OR REPLACE INTO media VALUES (?,?)",
                           (name, json.dumps(image) if image else None))
                db.execute("INSERT OR REPLACE INTO media_checks VALUES (?,?,unixepoch())",
                           (name, "credited" if image else "no_credit"))
            db.commit()
    finally:
        api.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dump", type=Path)
    parser.add_argument("--corpus", type=Path, default=Path("data/processed/m2-v1"))
    parser.add_argument("--output", type=Path, default=DEFAULT_PATH)
    parser.add_argument("--pilot", action="store_true")
    parser.add_argument("--enrich-only", action="store_true")
    parser.add_argument("--user-agent")
    args = parser.parse_args()
    if not args.enrich_only and not args.dump:
        parser.error("--dump richiesto")
    if args.pilot and args.output == DEFAULT_PATH:
        parser.error("Specificare --output per il pilota")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=args.output.parent) as tmp:
        stage = Path(tmp) / "catalog.sqlite3"
        with closing(sqlite3.connect(stage)) as db:
            if args.enrich_only or args.output.exists():
                with closing(sqlite3.connect(args.output.resolve().as_uri()+"?mode=ro", uri=True)) as old:
                    if args.enrich_only:
                        old.backup(db)
                    else:
                        checks = old.execute("SELECT * FROM media_checks").fetchall() if old.execute(
                            "SELECT 1 FROM sqlite_master WHERE name='media_checks'").fetchone() else []
                        cached = old.execute("SELECT name,data FROM media").fetchall()
            if not args.enrich_only:
                build(db, args.corpus, args.dump, args.pilot)
                if args.output.exists():
                    db.executemany("INSERT INTO media VALUES (?,?)", cached)
                    db.execute("CREATE TABLE media_checks(name TEXT PRIMARY KEY, status TEXT, checked INTEGER)")
                    db.executemany("INSERT INTO media_checks VALUES (?,?,?)", checks)
            db.commit()
            try:
                enrich(db, args.user_agent)
            except (httpx.HTTPError, ValueError) as exc:
                print("Wikimedia indisponibile; riprendere con --enrich-only:", exc.__class__.__name__,
                      getattr(getattr(exc, "response", None), "status_code", ""))
            print(dict(zip(("pages","structured","candidates","credited"), db.execute(
                "SELECT count(*),count(payload),count(file),count(media.data) FROM pages LEFT JOIN media ON file=name"
            ).fetchone())))
        os.replace(stage, args.output)


if __name__ == "__main__":
    main()
