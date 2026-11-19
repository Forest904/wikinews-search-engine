"""Compare semantic variants with E1 over the exact same candidate corpus."""

import argparse
import json
import math
import statistics
import time
from pathlib import Path

from wikinews_ir.evaluation.runs import load_queries
from wikinews_ir.ingestion.corpus import checksum
from wikinews_ir.models import SearchRequest
from wikinews_ir.retrieval.engine import RetrievalEngine
from wikinews_ir.retrieval.profiles import digest, index_name
from wikinews_ir.retrieval.query_builder import build_query
from wikinews_ir.semantic import ALIAS, call, client, collection_for, search
from wikinews_ir.semantic_cli import package_rows, read


def dcg(grades):
    return sum(grade / math.log2(i + 2) for i, grade in enumerate(grades))


def collection_state():
    with client("qdrant") as db:
        name = collection_for(db, ALIAS)
        info = call(db, "GET", "/collections/" + name)["result"]
        return {
            "collection": name,
            **{
                key: info.get(key)
                for key in (
                    "status",
                    "points_count",
                    "indexed_vectors_count",
                    "segments_count",
                    "config",
                )
            },
        }


def benchmark(args):
    first = read(args.natural / "manifest.json")
    before = collection_state()
    if args.require_indexed and not before["indexed_vectors_count"]:
        raise ValueError("Qdrant non dichiara vettori indicizzati nella collezione natural")
    manifests = [first]
    variants = [("natural", "natural", True, first), ("natural_indexed", "natural", False, first)]
    if first["variant"] != "natural":
        raise ValueError("Specificare il pacchetto natural")
    if args.stem:
        second = read(args.stem / "manifest.json")
        if second["variant"] != "stem":
            raise ValueError("Specificare il pacchetto stem")
        for field in (
            "selection",
            "limit",
            "corpus_sha256",
            "encoder",
            "count",
            "cleaning_version",
        ):
            if first[field] != second[field]:
                raise ValueError(f"Pacchetti non confrontabili: {field}")
        manifests.append(second)
        variants.insert(1, ("stem", "stem", True, second))
    judgments = {}
    for line in args.qrels.read_text("utf-8").splitlines():
        qid, _, doc, grade = line.split()
        judgments.setdefault(qid, {})[doc] = int(grade)
    backend = RetrievalEngine()
    rows = []
    try:
        metadata = backend.metadata("E1")
        if metadata["corpus_sha256"] != first["corpus_sha256"]:
            raise ValueError("Indice E1 di un altro corpus")
        ids = {r["document_id"] for batch in package_rows(args.natural, first) for r in batch}
        if args.stem and ids != {
            r["document_id"] for batch in package_rows(args.stem, second) for r in batch
        }:
            raise ValueError("Documenti diversi nei pacchetti natural e stem")
        candidates = sorted(ids)
        for q in load_queries(args.queries):
            qid, query = q["query_id"], q["query"]
            if qid not in judgments:
                continue
            query_body = build_query(query, "E1")
            if len(candidates) != metadata["document_count"]:
                # Each ids query must stay below Elasticsearch's max_result_window.
                chunks = [
                    {"ids": {"values": candidates[i : i + 10000]}}
                    for i in range(0, len(candidates), 10000)
                ]
                query_body = {
                    "bool": {
                        "must": [query_body],
                        "filter": [{"bool": {"should": chunks, "minimum_should_match": 1}}],
                    }
                }
            started = time.perf_counter()
            lexical = backend.client.search(
                index=index_name(backend.settings, "E1"),
                size=10,
                query=query_body,
                sort=[{"_score": "desc"}, {"document_id": "asc"}],
            )
            rankings = {"E1": [r["_id"] for r in lexical["hits"]["hits"]]}
            timings = {}
            latencies = {"E1": (time.perf_counter() - started) * 1000}
            for label, variant, exact, manifest in variants:
                request = SearchRequest(query=query, profile="semantic")
                stages = {}
                started = time.perf_counter()
                result = search(request, variant=variant, exact=exact, timings=stages)
                latencies[label] = (time.perf_counter() - started) * 1000
                timings[label] = stages

                if f"-{digest(manifest)[:16]}-" not in result.index:
                    raise ValueError("Alias diverso dal pacchetto selezionato")
                rankings[label] = [r.document_id for r in result.hits]
            grades = judgments[qid]
            ideal = dcg(sorted((g for doc, g in grades.items() if doc in ids), reverse=True)[:10])
            for label, ranking in rankings.items():
                rows.append(
                    {
                        "query_id": qid,
                        "profile": label,
                        "ranking": ranking,
                        "ndcg@10": dcg([grades.get(doc, 0) for doc in ranking]) / ideal
                        if ideal
                        else None,
                        "judged": sum(doc in grades for doc in ranking),
                        "returned": len(ranking),
                        "unjudged": [doc for doc in ranking if doc not in grades],
                        "elapsed_ms": latencies[label],
                        "stages": timings.get(label, {}),
                        "exact_overlap": len(set(ranking) & set(rankings["natural"]))
                        if label == "natural_indexed"
                        else None,
                    }
                )
    finally:
        backend.close()
    if not rows:
        raise ValueError("Nessuna query giudicata")
    summary = {}
    for label in rankings:
        group = [r for r in rows if r["profile"] == label]
        scores = [r["ndcg@10"] for r in group if r["ndcg@10"] is not None]
        delays = sorted(r["elapsed_ms"] for r in group)
        summary[label] = {
            "mean_ndcg@10": statistics.mean(scores) if scores else None,
            "topics_with_positive_ideal": len(scores),
            "topics": len(group),
            "judged": sum(r["judged"] for r in group),
            "returned": sum(r["returned"] for r in group),
            "p50_ms": statistics.median(delays),
            "p95_ms": delays[math.ceil(0.95 * len(delays)) - 1],
        }
        if label == "natural_indexed":
            exact = {r["query_id"]: len(r["ranking"]) for r in rows if r["profile"] == "natural"}
            overlaps = [
                r["exact_overlap"] / exact[r["query_id"]] for r in group if exact[r["query_id"]]
            ]
            summary[label]["mean_recall_exact@10"] = statistics.mean(overlaps) if overlaps else None
    return {
        "candidates": len(ids),
        "qdrant_before": before,
        "qdrant_after": collection_state(),
        "queries_sha256": checksum(args.queries),
        "qrels_sha256": checksum(args.qrels),
        "corpus_sha256": first["corpus_sha256"],
        "packages": {m["variant"]: digest(m) for m in manifests},
        "summary": summary,
        "queries": rows,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stem", type=Path)
    parser.add_argument("--require-indexed", action="store_true")
    for key in ("queries", "qrels", "natural", "output"):
        parser.add_argument("--" + key, required=True, type=Path)
    args = parser.parse_args()
    report = benchmark(args)
    args.output.parent.mkdir(exist_ok=True, parents=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], indent=2))
