"""Rebuild the blind pilot from M2 and archived E0–E4 pool; never imports labels."""

import argparse
import json
import tempfile
from pathlib import Path

from wikinews_ir.evaluation.artifacts import (
    encoded,
    file_sha,
    jsonl,
    read_rows,
    verify_bundle,
    write_bundle,
)
from wikinews_ir.evaluation.benchmark import corpus_data, document, load_protocol, load_topics


def prepare(topics, protocol, corpus, pool, selection, output):
    identity, docs = corpus_data(corpus)
    meta = verify_bundle(pool, "pool")["metadata"]
    if meta["corpus"] != identity or meta["topics_sha256"] != file_sha(topics):
        raise ValueError("Pool incompatibile")
    candidates = {(r["query_id"], r["document_id"]): r for r in read_rows(Path(pool) / "pool.jsonl")}
    chosen = read_rows(selection)
    topic_rows = load_topics(topics)
    pairs, documents, provenance = [], {}, []
    for topic in topic_rows:
        rows = [r for r in chosen if r["query_id"] == topic["query_id"]]
        if len(rows) != 6 or sum(r["method"] == "retrieved" for r in rows) != 3:
            raise ValueError("Richieste tre coppie recuperate e tre diagnostiche per topic")
        for row in rows:
            key = row["query_id"], row["document_id"]
            if row["method"] == "retrieved" and key not in candidates:
                raise ValueError("Documento non recuperato")
            doc = document(docs[row["document_id"]])
            documents[doc["document_id"]] = doc
            pairs.append({"query_id": key[0], "document_id": key[1]})
            provenance.append({**row, "retrieval": candidates.get(key, {}).get("provenance", []),
                               "revision_id": doc["revision_id"], "body_sha256": doc["body_sha256"]})
    if len({(r["query_id"], r["document_id"]) for r in pairs}) != 24:
        raise ValueError("Richieste 24 coppie distinte")
    payload = {"protocol": load_protocol(protocol), "topics": topic_rows,
               "documents": [documents[k] for k in sorted(documents)], "pairs": pairs}
    from wikinews_ir.evaluation.silver import validate_payload
    validate_payload(payload)
    output = Path(output)
    if output.exists():
        raise ValueError("Output già esistente")
    # Coordinator provenance is outside the blind packet directory.
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent) as temp:
        staging = Path(temp) / "pilot"
        write_bundle(staging / "provenance", "pilot-selection", {
            "selection.jsonl": jsonl(provenance)}, {"corpus": identity, "seed": "m5c-pilot-1",
            "pool_manifest_sha256": file_sha(Path(pool) / "manifest.json"),
            "selection_sha256": file_sha(selection), "labels_imported": False})
        manifest = write_bundle(staging / "packet", "packet", {"packet.json": encoded(payload)},
                                {"corpus": identity, "purpose": "real-local-calibration", "fixture": False,
                                 "selection_manifest_sha256": file_sha(staging / "provenance" / "manifest.json")})
        staging.rename(output)
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("topics", "protocol", "corpus", "pool", "selection", "output"):
        parser.add_argument("--" + field, required=True, type=Path)
    print(json.dumps(prepare(**vars(parser.parse_args())), indent=2))
