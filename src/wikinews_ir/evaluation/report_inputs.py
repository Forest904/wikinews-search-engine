"""Read verified ranking and judgment artifacts for one evaluation split."""

import math
from collections import defaultdict

from .artifacts import read_rows, verify_bundle


def require_file(manifest, name):
    if name not in manifest["artifacts"]:
        raise ValueError(f"File assente dal manifest: {name}")


def load_labels(directory, source, all_ids, selected_ids, split):
    manifest = verify_bundle(directory)
    meta = manifest["metadata"]
    detailed = manifest["kind"] == "annotation-gold-export"
    if detailed:
        if source != "gold" or meta["split"] != split:
            raise ValueError("Fonte o split incompatibile con l'export gold")
    elif manifest["kind"] != "qrels" or meta["source"] != source:
        raise ValueError("Fonte qrels incompatibile")
    name = f"qrels_{source}.tsv"
    require_file(manifest, name)
    labels = {}
    for line in (directory / name).read_text("utf-8").splitlines():
        qid, marker, doc, grade = line.split()
        key = qid, doc
        if (qid not in all_ids or marker != "0" or grade not in {"0", "1", "2"}
                or key in labels or (detailed and qid not in selected_ids)):
            raise ValueError("Qrels incompatibili o duplicati")
        labels[key] = int(grade)
    abstained = None
    if detailed:
        require_file(manifest, "judgments.jsonl")
        abstained = {(r["query_id"], r["document_id"])
                     for r in read_rows(directory / "judgments.jsonl")
                     if r["final"] and r["status"] == "needs_review"}
        if abstained & labels.keys():
            raise ValueError("Astensione con grado")
        total = len(abstained)
    else:
        total = meta["abstentions"]
    return ({k: v for k, v in labels.items() if k[0] in selected_ids}, abstained, total)


def load_rankings(directory, topics):
    manifest = verify_bundle(directory)
    queries = {t["query_id"]: t["query"] for t in topics}
    profiles = []
    if manifest.get("kind") == "external-run":
        meta = manifest["metadata"]
        profiles.append(("wikimedia", "wikimedia.trec", meta["queries"], None))
        limit = meta["top_k"]
    else:
        if not manifest.get("profiles"):
            raise ValueError("Bundle run incompatibile")
        limit = manifest["top_k"]
        for profile, meta in manifest["profiles"].items():
            records = [r for r in manifest["queries"] if r["profile"] == profile]
            counts = {r["query_id"]: r["exported"] for r in records}
            if len(counts) != len(records):
                raise ValueError("Query duplicata nel manifest")
            profiles.append((f"{profile}-v{meta['profile_version']}", f"{profile}.trec",
                             {r["query_id"]: r["query"] for r in records}, counts))
    for tag, name, declared, counts in profiles:
        require_file(manifest, name)
        if declared != queries:
            raise ValueError("Le query della run differiscono dal file dei topic")
        docs = defaultdict(dict)
        for line in (directory / name).read_text("utf-8").splitlines():
            qid, marker, doc, rank, score, run_id = line.split()
            rank = int(rank)
            if (qid not in queries or marker != "Q0" or run_id != tag or doc in docs[qid]
                    or not 1 <= rank <= limit or not math.isfinite(float(score))):
                raise ValueError("Run TREC non valida")
            docs[qid][doc] = rank
        ranking = {}
        for qid in queries:
            ranks = docs[qid]
            ordered = sorted(ranks, key=ranks.get)
            if ([ranks[d] for d in ordered] != list(range(1, len(ranks) + 1))
                    or (counts is not None and len(ranks) != counts[qid])):
                raise ValueError("Rank o conteggio incompatibile")
            ranking[qid] = ordered
        yield tag, ranking
