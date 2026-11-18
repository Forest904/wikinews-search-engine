"""Create synthetic offline inputs for the documented M6-A example."""

import argparse
from pathlib import Path

from wikinews_ir.evaluation.artifacts import encoded, file_sha, jsonl, write_bundle


def create(root):
    root.mkdir(parents=True, exist_ok=False)
    topics = []
    for qid, kind, split in (("E", "event-specific", "development"),
                             ("T", "topical", "development"), ("U", "topical", "development"),
                             ("X", "event-specific", "test")):
        topics.append(dict(query_id=qid, query=f"Notizia {qid}", information_need="Fixture",
                           narrative="Valutazione sintetica", type=kind, split=split,
                           event_family=qid, theme="fixture", temporal_constraints={},
                           relevance_criteria={"0": "Assente", "1": "Secondario", "2": "Centrale"},
                           exclusion_criteria=["Fuori tema"]))
    (root/"topics.jsonl").write_text(jsonl(topics), encoding="utf-8")
    queries = {t["query_id"]: t["query"] for t in topics}
    for name, documents in (("profile", ["a", "b"]), ("external", ["b", "a"])):
        tag = "E0-v1" if name == "profile" else "wikimedia"
        trec = "".join(f"E Q0 {doc} {i} 1 {tag}\n" for i, doc in enumerate(documents, 1))
        if name == "profile":
            # Local run exports predate the common benchmark bundle format.
            directory = root/name
            directory.mkdir()
            (directory/"E0.trec").write_text(trec, encoding="utf-8")
            records = [dict(query_id=q, query=text, profile="E0", exported=2 if q == "E" else 0)
                       for q, text in queries.items()]
            (directory/"manifest.json").write_text(encoded(dict(
                profiles={"E0": {"profile_version": "1"}}, queries=records, top_k=10,
                artifacts={"E0.trec": file_sha(directory/"E0.trec")})), encoding="utf-8")
        else:
            write_bundle(root/name, "external-run", {"wikimedia.trec": trec},
                         dict(queries=queries, top_k=10, complete=True))
    write_bundle(root/"gold", "annotation-gold-export", {
        "qrels_gold.tsv": "E 0 b 2\nT 0 c 0\nT 0 d 1\n",
        "judgments.jsonl": jsonl([dict(query_id="E", document_id="a", final=True,
                                       status="needs_review")])}, {"split": "development"})
    write_bundle(root/"silver", "qrels", {
        "qrels_silver.tsv": "E 0 b 1\nT 0 c 0\nT 0 e 2\nX 0 x 2\n"},
        dict(source="silver", graded=4, abstentions=1))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    create(parser.parse_args().directory)
