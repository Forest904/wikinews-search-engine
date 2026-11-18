"""Benchmark HTTP sequenziale sul corpus M2 (eseguire dalla radice del repository)."""

import argparse
import json
import math
import platform
from importlib.metadata import version
from pathlib import Path
from statistics import median
from time import perf_counter

import httpx

from wikinews_ir.evaluation.runs import load_queries
from wikinews_ir.ingestion.corpus import checksum
from wikinews_ir.ingestion.indexer import execution, validate_corpus
from wikinews_ir.models import SearchResponse
from wikinews_ir.retrieval.engine import RetrievalEngine
from wikinews_ir.retrieval.profiles import SUPPORTED_PROFILES

QUERIES = Path("configs/smoke/m4-queries.jsonl")
CORPUS = Path("data/processed/m2-v1")
SESSIONS = (1, 2)
REPEATS = 5
PAGE_SIZE = 10


def request_sample(client, row, profile, expected):
    params = dict(q=row["query"], profile=profile, page=1, page_size=PAGE_SIZE)
    sample = dict(status=None, error=None, client_ms=None, es_ms=None)
    start = perf_counter()
    try:
        response = client.get("/api/search", params=params)
        sample["client_ms"] = (perf_counter() - start) * 1000
        sample["status"] = response.status_code
        response.raise_for_status()
        result = SearchResponse.model_validate_json(response.content)
        if (result.metadata != expected or result.index != expected["index"]
                or result.profile != profile or result.query != row["query"]
                or result.page != 1 or result.page_size != PAGE_SIZE):
            raise ValueError("Identità ricerca o indice inattesa")
        sample["es_ms"] = result.elapsed_ms
    except (httpx.HTTPError, ValueError) as exc:
        if sample["client_ms"] is None:
            sample["client_ms"] = (perf_counter() - start) * 1000
        sample["error"] = f"{type(exc).__name__}: {exc}"
    return sample


def session_samples(client, session, queries, profiles):
    for profile, metadata in profiles.items():
        for iteration in range(REPEATS + 1):
            for row in queries:
                yield dict(session=session, phase="measure" if iteration else "warmup",
                           iteration=iteration, profile=profile, **row,
                           **request_sample(client, row, profile, metadata))


def summarize(samples):
    measured = [s for s in samples if s["phase"] == "measure"]
    valid = [s for s in measured if s["error"] is None]
    summary = dict(requests=len(measured), errors=len(measured) - len(valid),
                   warmup_errors=sum(s["error"] is not None for s in samples
                                     if s["phase"] == "warmup"))
    for key in ("client_ms", "es_ms"):
        values = sorted(s[key] for s in valid)
        summary[key] = (dict(median=median(values), p95=values[math.ceil(.95 * len(values)) - 1])
                        if values else dict(median=None, p95=None))
    return summary


def report(summaries):
    lines = ["# M4-P — Latenze per profilo", "",
             "Valori in ms. Δ = sessione 2 meno sessione 1. P95 nearest-rank.", ""]
    for key, label in (("client_ms", "Client HTTP"), ("es_ms", "Elasticsearch")):
        lines.extend([f"## {label}", "",
                      "| Profilo | Richieste 1/2 | Errori misura 1/2 | Errori warmup 1/2 |"
                      " Mediana 1 | Mediana 2 | Δ mediana | p95 1 | p95 2 | Δ p95 |",
                      "|---|---|---|---|---:|---:|---:|---:|---:|---:|"])
        for profile in SUPPORTED_PROFILES:
            first, second = (summaries[n][profile] for n in SESSIONS)
            cells = [profile] + [f"{first[k]}/{second[k]}"
                                 for k in ("requests", "errors", "warmup_errors")]
            for metric in ("median", "p95"):
                a, b = first[key][metric], second[key][metric]
                delta = None if a is None or b is None else b - a
                cells.extend("—" if v is None else f"{v:.2f}" for v in (a, b, delta))
            lines.append("| " + " | ".join(cells) + " |")
        lines.append("")
    return "\n".join(lines)


def benchmark(output, base_url):
    if output.exists():
        raise FileExistsError(f"Usare una directory nuova: {output}")
    queries = load_queries(QUERIES)
    identity = validate_corpus(CORPUS)
    backend = RetrievalEngine()
    try:
        ready = backend.readiness()
        profiles = {p: ready[p] for p in SUPPORTED_PROFILES}
        for meta in profiles.values():
            if meta["document_count"] != 11032 or any(meta[k] != v for k, v in identity.items()):
                raise ValueError("Gli indici configurati devono contenere il corpus M2")
        es_version = backend.client.info()["version"]["number"]
    finally:
        backend.close()
    with httpx.Client(base_url=base_url, timeout=10) as client:
        for profile, meta in profiles.items():
            probe = request_sample(client, queries[0], profile, meta)
            if probe["error"]:
                raise ValueError(f"Preflight API {profile}: {probe['error']}")

    manifest = dict(**execution(), platform=platform.platform(), cpu=platform.processor(),
                    elasticsearch=es_version, httpx=version("httpx"), fastapi=version("fastapi"),
                    base_url=base_url, corpus=identity, profiles=profiles,
                    queries=str(QUERIES), queries_sha256=checksum(QUERIES),
                    profile_order=list(profiles), sessions=2, warmup_passes=1,
                    measured_passes=REPEATS, page=1, page_size=PAGE_SIZE, concurrency=1,
                    timeout_seconds=10, complete=False)
    output.mkdir(parents=True)
    manifest_path = output / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    summaries = {}
    with (output / "samples.jsonl").open("w", encoding="utf-8") as stream:
        for session in SESSIONS:
            samples = []
            with httpx.Client(base_url=base_url, timeout=10) as client:
                for sample in session_samples(client, session, queries, profiles):
                    stream.write(json.dumps(sample, ensure_ascii=False) + "\n")
                    samples.append(sample)
            summaries[session] = {p: summarize([s for s in samples if s["profile"] == p])
                                  for p in profiles}
    complete = all(not (s["errors"] or s["warmup_errors"])
                   for group in summaries.values() for s in group.values())
    (output / "report.md").write_text(report(summaries), encoding="utf-8")
    manifest.update(complete=complete, summaries=summaries, samples_sha256=checksum(
        output / "samples.jsonl"))
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return complete


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    raise SystemExit(0 if benchmark(args.output, args.base_url) else 1)
