"""Local corpus verification, timing and review samples (not a relevance benchmark)."""

import argparse
import json
import math
import platform
import statistics
from pathlib import Path
from time import perf_counter

from wikinews_ir.evaluation.runs import export_runs, load_queries
from wikinews_ir.ingestion.indexer import build_indices, execution
from wikinews_ir.models import SearchRequest
from wikinews_ir.retrieval.engine import RetrievalEngine
from wikinews_ir.retrieval.profiles import SUPPORTED_PROFILES


def verify(corpus, queries, output, rebuild):
    if output.exists():
        raise ValueError("Usare una nuova directory di output")
    output.mkdir(parents=True)
    backend = RetrievalEngine()
    try:
        report = {"execution": execution(), "platform": platform.platform(),
                  "machine": platform.machine(), "timings": {}, "samples": []}
        report["indices"] = build_indices(backend, corpus, output=output / "indices")
        first = export_runs(backend, queries, output / "run-first", profiles=SUPPORTED_PROFILES)
        repeat = export_runs(backend, queries, output / "run-repeat", profiles=SUPPORTED_PROFILES)
        assert first["artifacts"] == repeat["artifacts"], "Ranking ripetuti diversi"
        report["repeat_identical"] = True
        if rebuild:
            report["rebuilt_indices"] = build_indices(
                backend, corpus, rebuild=True, output=output / "indices"
            )
            rebuilt = export_runs(backend, queries, output / "run-rebuilt", profiles=SUPPORTED_PROFILES)
            assert first["artifacts"] == rebuilt["artifacts"], "Ranking dopo rebuild diversi"
            report["rebuild_identical"] = True
        rows = load_queries(queries)
        for profile in SUPPORTED_PROFILES:
            for row in rows:
                backend.search(SearchRequest(query=row["query"], profile=profile))
            times = []
            for _ in range(5):
                for row in rows:
                    start = perf_counter()
                    backend.search(SearchRequest(query=row["query"], profile=profile))
                    times.append((perf_counter() - start) * 1000)
            report["timings"][profile] = {
                "samples": len(times), "p50_ms": statistics.median(times),
                "p95_ms": sorted(times)[math.ceil(len(times) * 0.95) - 1],
                "definition": "RetrievalEngine wall time including metadata validation; warm",
            }
            for row in rows:
                result = backend.search(SearchRequest(query=row["query"], profile=profile, page_size=5))
                report["samples"].append({
                    **row, "profile": profile, "total": result.total,
                    "hits": [{**hit.model_dump(), "body": backend.get_article(hit.document_id, profile).body}
                             for hit in result.hits],
                })
        baseline = export_runs(backend, Path("configs/smoke/queries.jsonl"),
                               output / "baseline-regression", profiles=("E0", "E1"))
        expected = {
            "E0.trec": "229f89606b4311e1aff548f384dbc97949af65cc0b90a5157fccadffb304b0ad",
            "E1.trec": "05e68e06d6546155a09c50a17fd290f0016705c906c5a6a7279b9cbf7bdba39b",
        }
        if baseline["artifacts"] != expected:
            raise ValueError("Regressione baseline M3: hash TREC diversi")
        report["baseline_m3_identical"] = True
        report["run_hashes"] = first["artifacts"]
        (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({k: report[k] for k in ("timings", "run_hashes")}, indent=2))
    finally:
        backend.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=Path("data/processed/m2-v1"))
    parser.add_argument("--queries", type=Path, default=Path("configs/smoke/m4-queries.jsonl"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--rebuild", action="store_true", help="Ricostruisce i due indici configurati")
    args = parser.parse_args()
    verify(args.corpus, args.queries, args.output, args.rebuild)
