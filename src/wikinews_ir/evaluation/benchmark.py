"""Offline benchmark preparation, pooling and packet construction."""

import math
import random
from pathlib import Path

import yaml

from wikinews_ir.evaluation.artifacts import (
    encoded,
    file_sha,
    jsonl,
    read_rows,
    sha,
    verify_bundle,
    write_bundle,
)
from wikinews_ir.evaluation.contracts import Candidate, Document, Protocol, Topic
from wikinews_ir.ingestion.indexer import articles, validate_corpus


def load_topics(path):
    topics = [Topic.model_validate(r).model_dump() for r in read_rows(path)]
    ids, families = set(), {}
    if not topics:
        raise ValueError("Topic vuoti")
    for topic in topics:
        if topic["query_id"] in ids:
            raise ValueError("query_id duplicato")
        ids.add(topic["query_id"])
        family = topic["event_family"]
        if family in families and families[family] != topic["split"]:
            raise ValueError("Famiglia condivisa fra split")
        families[family] = topic["split"]
    return topics


def load_protocol(path):
    return Protocol.model_validate(yaml.safe_load(Path(path).read_text("utf-8"))).model_dump()


def queries(topics_path, protocol_path, output):
    topics, protocol = load_topics(topics_path), load_protocol(protocol_path)
    return write_bundle(output, "queries", {
        "queries.jsonl": jsonl([{"query_id": t["query_id"], "query": t["query"]}
                                for t in topics]),
    }, {"topics_sha256": file_sha(topics_path), "protocol": protocol})


def document(article):
    fields = {k: article[k] for k in ("document_id", "revision_id", "title", "body",
              "publication_date", "publication_date_status", "publication_date_evidence")}
    fields["body_sha256"] = sha(fields["body"])
    return Document.model_validate(fields).model_dump()


def corpus_data(corpus):
    identity = validate_corpus(corpus)
    return identity, {r["document_id"]: r for r in articles(Path(corpus) / "articles.ndjson")}


def reconcile(pilot, corpus, output):
    pilot = Path(pilot)
    identity, docs = corpus_data(corpus)
    themes = {"P01": "disastri naturali", "P02": "energia", "P03": "politica",
              "P04": "disastri naturali"}
    topics = []
    for row in read_rows(pilot / "topics.jsonl"):
        adapted = dict(row)
        adapted["query_id"] = adapted.pop("topic_id")
        adapted["selection_rationale"] = adapted.pop("topic_selection_rationale", "")
        adapted.update(theme=themes.get(adapted["query_id"], "da rivedere"),
                       event_family=f"calibration-{adapted['query_id']}", split="calibration")
        topics.append(Topic.model_validate(adapted).model_dump())
    external = {str(r["doc_id"]): r for r in read_rows(pilot / "documents.jsonl")}
    topic_ids = {t["query_id"] for t in topics}
    if len(topic_ids) != len(topics):
        raise ValueError("Topic pilot duplicati")
    report, pairs, selected, seen = [], [], {}, set()
    for row in read_rows(pilot / "candidates.jsonl"):
        identifier = str(row["doc_id"])
        key = row["topic_id"], identifier
        if key[0] not in topic_ids:
            raise ValueError("Topic pilot sconosciuto")
        if key in seen:
            raise ValueError("Coppia pilot duplicata")
        seen.add(key)
        current, previous = docs.get(identifier), external.get(identifier)
        revision_match = bool(current and current["revision_id"] == str(row["version_id"]))
        if previous and str(previous.get("version_id", row["version_id"])) != str(row["version_id"]):
            raise ValueError("Revisione del documento esterno incoerente con il candidato")
        report.append({"query_id": key[0], "document_id": identifier,
                       "present": current is not None, "revision_match": revision_match,
                       "external_revision": str(row["version_id"]),
                       "current_revision": current["revision_id"] if current else None,
                       "text_equal": bool(current and previous and
                                          current["body"] == previous["text"]),
                       "external_body_sha256": sha(previous["text"]) if previous else None,
                       "current_body_sha256": sha(current["body"]) if current else None})
        if revision_match:
            selected[identifier] = document(current)
            pairs.append({"query_id": key[0], "document_id": identifier})
    return write_bundle(output, "reconciliation", {
        "topics.jsonl": jsonl(topics), "report.json": encoded(report),
        "documents.jsonl": jsonl([selected[k] for k in sorted(selected)]),
        "pairs.jsonl": jsonl(pairs),
    }, {"corpus": identity, "source_hashes": {
        n: file_sha(pilot / n) for n in ("topics.jsonl", "candidates.jsonl", "documents.jsonl")
    }, "source": str(pilot), "labels_imported": False,
        "pairs": len(report), "matched_revisions": len(pairs)})


def pool(topics_path, corpus, run_dirs, output):
    topics = load_topics(topics_path)
    wanted = {t["query_id"]: t["query"] for t in topics}
    identity, docs = corpus_data(corpus)
    merged, run_ids, inputs = {}, set(), {}

    def add(qid, did, run_id, rank):
        if qid not in wanted or did not in docs:
            raise ValueError("Run con query/documento sconosciuto")
        key = qid, did
        if key not in merged:
            merged[key] = dict(query_id=qid, document_id=did,
                               revision_id=docs[did]["revision_id"],
                               body_sha256=sha(docs[did]["body"]), provenance=[])
        merged[key]["provenance"].append({"run_id": run_id, "rank": rank})

    for directory in map(Path, run_dirs):
        manifest = verify_bundle(directory)
        inputs[str(directory)] = file_sha(directory / "manifest.json")
        if manifest.get("kind") == "external-run":
            meta = manifest["metadata"]
            if meta["corpus"] != identity or meta["queries"] != wanted:
                raise ValueError("Run esterna incompatibile")
            rid = "wikimedia"
            if rid in run_ids:
                raise ValueError("run_id duplicato")
            run_ids.add(rid)
            for row in read_rows(directory / "results.jsonl"):
                if row["in_corpus"]:
                    add(row["query_id"], row["document_id"], rid, row["rank"])
            continue
        for profile, metadata in manifest["profiles"].items():
            if f"{profile}.trec" not in manifest["artifacts"]:
                raise ValueError("Run non coperta dal manifest")
            if any(metadata.get(k) != v for k, v in identity.items()):
                raise ValueError("Corpus delle run incompatibile")
            records = [r for r in manifest["queries"] if r["profile"] == profile]
            if {r["query_id"]: r["query"] for r in records} != wanted or (
                len(records) != len(wanted)
            ):
                raise ValueError("Query delle run incompatibili")
            rid = f"{profile}-v{metadata['profile_version']}"
            if rid in run_ids:
                raise ValueError("run_id duplicato")
            run_ids.add(rid)
            seen, ranks, counts = set(), {}, dict.fromkeys(wanted, 0)
            for line in (directory / f"{profile}.trec").read_text("utf-8").splitlines():
                qid, marker, did, rank, score, tag = line.split()
                rank = int(rank)
                if marker != "Q0" or tag != rid or not math.isfinite(float(score)) or (
                    rank != ranks.get(qid, 0) + 1 or rank > manifest["top_k"]
                ) or (qid, did) in seen:
                    raise ValueError("Run TREC non valida")
                seen.add((qid, did))
                ranks[qid] = rank
                add(qid, did, rid, rank)
                counts[qid] += 1
            if any(counts[r["query_id"]] != r["exported"] for r in records):
                raise ValueError("Conteggio run diverso dal manifest")
    if not run_ids:
        raise ValueError("Nessuna run")
    result = [Candidate.model_validate(merged[k]).model_dump() for k in sorted(merged)]
    for row in result:
        row["provenance"].sort(key=lambda p: (p["run_id"], p["rank"]))
    return write_bundle(output, "pool", {"pool.jsonl": jsonl(result)}, {
        "corpus": identity, "topics_sha256": file_sha(topics_path), "inputs": inputs,
        "queries": wanted, "run_ids": sorted(run_ids), "pairs": len(result),
        "coverage": {rid: sum(any(p["run_id"] == rid for p in r["provenance"])
                              for r in result) for rid in sorted(run_ids)},
    })


def select(pool_dir, output, quotas=None, seed=None, exclude_pairs=None):
    manifest = verify_bundle(pool_dir, "pool")
    candidates = [Candidate.model_validate(r).model_dump()
                  for r in read_rows(Path(pool_dir) / "pool.jsonl")]
    chosen, allocations = {}, []
    if exclude_pairs is not None:
        excluded = {(r["query_id"], r["document_id"]) for r in read_rows(exclude_pairs)}
        candidates = [r for r in candidates if (r["query_id"], r["document_id"]) not in excluded]
    if quotas is None:
        for row in candidates:
            row["selection"] = ["all"]
            chosen[row["query_id"], row["document_id"]] = row
    else:
        if type(seed) is not int or set(quotas) != set(manifest["metadata"]["run_ids"]):
            raise ValueError("Seed e quote esplicite per tutte le run richiesti")
        if any(type(q) is not int or q < 0 for q in quotas.values()):
            raise ValueError("Quote non valide")
        for qid in sorted(manifest["metadata"]["queries"]):
            for rid in sorted(quotas):
                available = sorted([r for r in candidates if r["query_id"] == qid and
                                    any(p["run_id"] == rid for p in r["provenance"])],
                                   key=lambda r: r["document_id"])
                rng = random.Random(sha(f"{seed}:{qid}:{rid}"))
                sample = rng.sample(available, min(quotas[rid], len(available)))
                allocations.append(dict(query_id=qid, run_id=rid, requested=quotas[rid],
                                        available=len(available), sampled=len(sample)))
                for row in sample:
                    key = row["query_id"], row["document_id"]
                    chosen.setdefault(key, row)["selection"].append(rid)
    return write_bundle(output, "selection", {
        "selection.jsonl": jsonl([chosen[k] for k in sorted(chosen)]),
        "allocations.json": encoded(allocations),
    }, {**manifest["metadata"], "pool_manifest_sha256": file_sha(Path(pool_dir)/"manifest.json"),
        "quotas": quotas, "seed": seed, "selected_pairs": len(chosen),
        **({"excluded_pairs_sha256": file_sha(exclude_pairs)} if exclude_pairs else {})})


def packet(topics_path, protocol_path, selection_dir, corpus, output):
    topics, protocol = load_topics(topics_path), load_protocol(protocol_path)
    selection = verify_bundle(selection_dir, "selection")
    identity, docs = corpus_data(corpus)
    if selection["metadata"]["corpus"] != identity or (
        selection["metadata"]["topics_sha256"] != file_sha(topics_path)
    ):
        raise ValueError("Selezione incompatibile con corpus/topic")
    candidates = [Candidate.model_validate(r).model_dump()
                  for r in read_rows(Path(selection_dir) / "selection.jsonl")]
    pairs, selected = [], {}
    for row in candidates:
        doc = document(docs[row["document_id"]])
        if any(row[k] != doc[k] for k in ("revision_id", "body_sha256")):
            raise ValueError("Documento candidato incompatibile")
        selected[doc["document_id"]] = doc
        pairs.append({"query_id": row["query_id"], "document_id": row["document_id"]})
    if not pairs:
        raise ValueError("Pacchetto vuoto")
    used = {p["query_id"] for p in pairs}
    payload = {"protocol": protocol, "topics": [t for t in topics if t["query_id"] in used],
               "documents": [selected[k] for k in sorted(selected)], "pairs": pairs}
    return write_bundle(output, "packet", {"packet.json": encoded(payload)}, {
        "corpus": identity,
        "selection_manifest_sha256": file_sha(Path(selection_dir) / "manifest.json"),
    })
