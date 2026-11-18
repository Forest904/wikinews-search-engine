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
from wikinews_ir.semantic import search
from wikinews_ir.semantic_cli import package_rows, read


def dcg(grades):
    return sum(grade / math.log2(i + 2) for i, grade in enumerate(grades))


def benchmark(args):
    manifests = [read(path / "manifest.json") for path in (args.natural, args.stem)]
    first, second = manifests
    if (first["variant"], second["variant"]) != ("natural", "stem"):
        raise ValueError("Specificare i pacchetti natural e stem")
    for field in ("selection", "limit", "corpus_sha256", "encoder", "count", "cleaning_version"):
        if first[field] != second[field]:
            raise ValueError(f"Pacchetti non confrontabili: {field}")
    judgments = {}
    for line in args.qrels.read_text("utf-8").splitlines():
        qid, _, doc, grade = line.split()
        judgments.setdefault(qid, {})[doc] = int(grade)
    backend = RetrievalEngine()
    rows = []
    try:
        if backend.metadata("E1")["corpus_sha256"] != first["corpus_sha256"]:
            raise ValueError("Indice E1 di un altro corpus")
        ids = {r["document_id"] for batch in package_rows(args.natural, first) for r in batch}
        for q in load_queries(args.queries):
            qid, query = q["query_id"], q["query"]
            if qid not in judgments:
                continue
            started = time.monotonic()
            lexical = backend.client.search(
                index=index_name(backend.settings, "E1"),
                size=10,
                query={
                    "bool": {
                        "must": [build_query(query, "E1")],
                        "filter": [{"ids": {"values": sorted(ids)}}],
                    }
                },
                sort=[{"_score": "desc"}, {"document_id": "asc"}],
            )
            rankings = {"E1": [r["_id"] for r in lexical["hits"]["hits"]]}
            latencies = {"E1": round((time.monotonic() - started) * 1000)}
            for label, variant, exact, manifest in (
                ("natural", "natural", True, first),
                ("stem", "stem", True, second),
                ("natural_indexed", "natural", False, first),
            ):
                result = search(
                    SearchRequest(query=query, profile="semantic"), variant=variant, exact=exact
                )

                if f"-{digest(manifest)[:16]}-" not in result.index:
                    raise ValueError("Alias diverso dal pacchetto selezionato")
                rankings[label] = [r.document_id for r in result.hits]
                latencies[label] = result.elapsed_ms
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
            "judged": sum(r["judged"] for r in group),
            "returned": sum(r["returned"] for r in group),
            "p50_ms": statistics.median(delays),
            "p95_ms": delays[math.ceil(0.95 * len(delays)) - 1],
        }
    return {
        "candidates": len(ids),
        "queries_sha256": checksum(args.queries),
        "qrels_sha256": checksum(args.qrels),
        "corpus_sha256": first["corpus_sha256"],
        "packages": {m["variant"]: digest(m) for m in manifests},
        "summary": summary,
        "queries": rows,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("queries", "qrels", "natural", "stem", "output"):
        parser.add_argument("--" + key, required=True, type=Path)
    args = parser.parse_args()
    report = benchmark(args)
    args.output.parent.mkdir(exist_ok=True, parents=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], indent=2))
