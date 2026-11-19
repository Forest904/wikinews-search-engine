"""Run a repeatable, single-client retrieval workload and retain every observation."""

import argparse
import json
import math
import platform
import random
import subprocess
import time
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from statistics import median

from wikinews_ir.ingestion.corpus import checksum
from wikinews_ir.models import SearchRequest
from wikinews_ir.retrieval.engine import RetrievalEngine

TOPICS = Path("benchmarks/topics/production-approved.jsonl")
CASES = Path("configs/evaluation/performance.jsonl")


def records(path):
    return [json.loads(line) for line in path.read_text("utf-8").splitlines() if line.strip()]


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), "utf-8")


def distribution(values):
    if not values:
        return {"n": 0}
    values = sorted(values)
    return {
        "n": len(values),
        "p50": median(values),
        "p95": values[math.ceil(0.95 * len(values)) - 1],
        "p99": values[math.ceil(0.99 * len(values)) - 1] if len(values) >= 1000 else None,
    }


def run(args):
    topics = [t for t in records(args.topics) if t["split"] == args.split]
    cases = [{"id": t["query_id"], "class": "topic", "query": t["query"]} for t in topics]
    cases += records(args.cases)
    if not topics or len({c["id"] for c in cases}) != len(cases):
        raise ValueError("Empty split or duplicate workload identifiers")
    profiles = args.profiles
    backend = RetrievalEngine()
    try:
        indices = {p: backend.metadata(p) for p in profiles if p != "semantic"}
        hashes = {m["corpus_sha256"] for m in indices.values()}
        if len(hashes) > 1:
            raise ValueError("Lexical profiles use different corpora")
        semantic = None
        if "semantic" in profiles:
            if not args.semantic_manifest:
                raise ValueError("--semantic-manifest required")
            semantic = json.loads(args.semantic_manifest.read_text("utf-8"))
            if hashes and (
                semantic["corpus_sha256"] not in hashes
                or any(semantic["count"] != m["document_count"] for m in indices.values())
            ):
                raise ValueError("Semantic and lexical candidate sets differ")
        args.output.mkdir(parents=True, exist_ok=False)
        manifest = dict(
            start=datetime.now(UTC).isoformat(),
            host=platform.platform(),
            processor=platform.processor(),
            python=platform.python_version(),
            commit=subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
            dirty=bool(subprocess.check_output(["git", "status", "--porcelain"])),
            seed=args.seed,
            profiles=profiles,
            sessions=args.sessions,
            distinct_warmup=args.distinct_warmup,
            repeats=args.repeats,
            cache_state=args.cache_state,
            split=args.split,
            topics_sha256=checksum(args.topics),
            runner_sha256=checksum(Path(__file__)),
            cases_sha256=checksum(args.cases),
            indices=indices,
            semantic=semantic,
        )
        write_json(args.output / "manifest.json", manifest)
        groups = defaultdict(list)
        errors = 0
        with (args.output / "samples.jsonl").open("x", encoding="utf-8") as output:
            for session in range(args.sessions):
                order = profiles[session % len(profiles) :] + profiles[: session % len(profiles)]
                for profile in order:
                    for iteration in range(args.repeats + 1):
                        shuffled = cases.copy()
                        if args.distinct_warmup and not iteration:
                            shuffled = [
                                {"id": "warmup", "class": "warmup", "query": "cronaca europea"}
                            ]
                        random.Random(args.seed + session * 10000 + iteration).shuffle(shuffled)
                        for case in shuffled:
                            params = {k: v for k, v in case.items() if k not in ("id", "class")}
                            req = SearchRequest(profile=profile, **params)
                            row = dict(
                                session=session,
                                iteration=iteration,
                                profile=profile,
                                case=case["id"],
                                category=case["class"],
                                error=None,
                                phase=(
                                    "warmup"
                                    if not iteration
                                    else "first_pass"
                                    if iteration == 1 and args.distinct_warmup
                                    else "repeat"
                                ),
                            )
                            started = time.perf_counter()
                            try:
                                result = backend.search(req)
                                row["ms"] = (time.perf_counter() - started) * 1000
                                ids = [hit.document_id for hit in result.hits]
                                if (
                                    result.query != req.query
                                    or result.profile != profile
                                    or result.page != req.page
                                    or result.page_size != req.page_size
                                    or len(set(ids)) != len(ids)
                                ):
                                    raise ValueError("Search response identity mismatch")
                                if profile == "semantic":
                                    from wikinews_ir.retrieval.profiles import digest

                                    if f"-{digest(semantic)[:16]}-" not in result.index:
                                        raise ValueError("Semantic index changed")
                                elif result.metadata != indices[profile]:
                                    raise ValueError("Lexical index changed")
                                row.update(ranking=ids, internal_ms=result.elapsed_ms)
                            except Exception as exc:
                                row.setdefault("ms", (time.perf_counter() - started) * 1000)
                                row["error"] = type(exc).__name__ + ": " + str(exc)
                                errors += 1
                            if iteration and not row["error"]:
                                groups[session, profile, case["class"]].append(row["ms"])
                            output.write(json.dumps(row, ensure_ascii=False) + "\n")
                        output.flush()
        write_json(
            args.output / "summary.json",
            {
                "errors": errors,
                "groups": [
                    dict(session=s, profile=p, category=c, **distribution(v))
                    for (s, p, c), v in groups.items()
                ],
            },
        )
        if errors:
            raise SystemExit(f"{errors} unsuccessful searches; inspect samples.jsonl")
    finally:
        backend.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--topics", type=Path, default=TOPICS)
    parser.add_argument("--cases", type=Path, default=CASES)
    parser.add_argument("--split", default="test")
    parser.add_argument(
        "--profiles",
        nargs="+",
        default=["E0", "E1", "E2", "E3", "E4"],
        choices=["E0", "E1", "E2", "E3", "E4", "semantic"],
    )
    parser.add_argument("--semantic-manifest", type=Path)
    parser.add_argument("--sessions", type=int, default=3)
    parser.add_argument(
        "--distinct-warmup",
        action="store_true",
        help="Warm services with a separate query before the first measured pass",
    )
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--cache-state", default="processo nuovo, cache servizi non azzerate")
    args = parser.parse_args()
    if min(args.sessions, args.repeats) < 1 or len(set(args.profiles)) != len(args.profiles):
        parser.error("Require positive session/repeat counts and distinct profiles")
    run(args)
