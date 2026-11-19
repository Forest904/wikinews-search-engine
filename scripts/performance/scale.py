"""Build isolated lexical indices from deterministic nested corpus samples."""

import argparse
import hashlib
import json
import subprocess
import sys
import time
import uuid
from dataclasses import replace
from pathlib import Path

from engine import write_json

from wikinews_ir.config import get_settings
from wikinews_ir.ingestion.corpus import checksum
from wikinews_ir.ingestion.indexer import build_indices, validate_corpus
from wikinews_ir.models import SearchRequest
from wikinews_ir.retrieval.engine import RetrievalEngine


def samples(source, output, seed):
    identity = validate_corpus(source)
    parent = json.loads((source / "manifest.json").read_text("utf-8"))
    source_file = source / "articles.ndjson"
    rank = []
    with source_file.open("rb") as stream:
        for line in stream:
            doc = json.loads(line)["document_id"]
            rank.append((hashlib.sha256(f"{seed}/{doc}".encode()).digest(), doc))
    ordered = sorted(rank)
    for percent in (10, 50, 100):
        size = max(1, len(ordered) * percent // 100)
        selected = {doc for _, doc in ordered[:size]}
        folder = output / str(percent)
        folder.mkdir()
        with source_file.open("rb") as stream, (folder / "articles.ndjson").open("xb") as dst:
            for line in stream:
                if json.loads(line)["document_id"] in selected:
                    dst.write(line)
        write_json(
            folder / "audit.json", dict(parent=identity, selection="sha256(seed/id)", seed=seed)
        )
        (folder / "decisions.ndjson").write_bytes(b"")
        artifacts = {f.name: checksum(f) for f in folder.iterdir()}
        write_json(
            folder / "manifest.json",
            dict(
                valid=True,
                mode="build",
                snapshot_id=identity["snapshot_id"],
                input_filename=parent["input_filename"],
                input_sha256=parent["input_sha256"],
                pipeline_version=identity["pipeline_version"],
                artifacts=artifacts,
                counts={"articles_produced": size},
                benchmark_subset_percent=percent,
            ),
        )
        yield percent, size, folder


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("corpus", type=Path)
    p.add_argument("output", type=Path)
    p.add_argument("--seed", type=int, default=2026)
    p.add_argument("--build", action="store_true")
    p.add_argument("--embeddings", action="store_true")
    args = p.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    prefix = "bench_" + uuid.uuid4().hex[:12]
    for percent, size, folder in samples(args.corpus, args.output, args.seed):
        if args.embeddings:
            start = time.perf_counter()
            package = folder / "vectors"
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "wikinews_ir.cli",
                    "semantic",
                    "generate",
                    "--corpus",
                    str(folder),
                    "--package",
                    str(package),
                ],
                check=True,
            )
            seconds = time.perf_counter() - start
            spec = json.loads((package / "manifest.json").read_text("utf-8"))
            write_json(
                folder / "embedding-cost.json",
                dict(
                    seconds=seconds,
                    count=spec["count"],
                    docs_per_second=spec["count"] / seconds,
                    encoder=spec["encoder"],
                    bytes=sum(f.stat().st_size for f in package.rglob("*") if f.is_file()),
                ),
            )
        if args.build:
            name = f"{prefix}_{percent}"
            backend = RetrievalEngine(replace(get_settings(), elasticsearch_italian_index=name))
            try:
                (report,) = build_indices(
                    backend, folder, profiles=("E1",), output=folder / "build"
                )
                stats = backend.client.indices.stats(index=name, metric="store")
                timings = []
                for query in ("Roma", "Italia", "terremoto") * 3:
                    start = time.perf_counter()
                    backend.search(SearchRequest(query=query, profile="E1"))
                    timings.append(dict(query=query, ms=(time.perf_counter() - start) * 1000))
                write_json(
                    folder / "scale.json",
                    dict(
                        index=name,
                        documents=size,
                        docs_per_second=size / report["duration_seconds"],
                        seconds=report["duration_seconds"],
                        bytes=stats["_all"]["primaries"]["store"]["size_in_bytes"],
                        queries=timings,
                    ),
                )
            finally:
                backend.close()
