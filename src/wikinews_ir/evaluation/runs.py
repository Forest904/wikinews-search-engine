"""Minimal offline ranking export; no judgments or benchmark selection."""

import json
import math
import tempfile
from pathlib import Path

from wikinews_ir.ingestion.corpus import checksum
from wikinews_ir.ingestion.indexer import execution
from wikinews_ir.models import SearchRequest
from wikinews_ir.retrieval.profiles import SUPPORTED_PROFILES


def load_queries(path):
    queries = []
    seen = set()
    for line in Path(path).read_text("utf-8").splitlines():
        row = json.loads(line)
        identifier = row["query_id"]
        if not isinstance(identifier, str) or not identifier or any(c.isspace() for c in identifier):
            raise ValueError("query_id deve essere una stringa senza spazi")
        if identifier in seen:
            raise ValueError("query_id duplicato")
        seen.add(identifier)
        queries.append({"query_id": identifier, "query": SearchRequest(query=row["query"]).query})
    if not queries:
        raise ValueError("File query vuoto")
    return queries


def export_runs(backend, queries_path, output, top_k=100, profiles=SUPPORTED_PROFILES):
    if not 1 <= top_k <= 1000:
        raise ValueError("top-k deve essere tra 1 e 1000")
    queries = load_queries(queries_path)
    output = Path(output)
    if output.exists():
        raise ValueError("La directory di output esiste già")
    ready = backend.readiness()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent, prefix=".run-") as temp:
        staging = Path(temp) / "result"
        staging.mkdir()
        manifest = {
            "execution": execution(), "queries_sha256": checksum(queries_path),
            "top_k": top_k, "profiles": {p: ready[p] for p in profiles},
            "elasticsearch_version": backend.client.info()["version"]["number"],
            "sort": ["_score desc", "document_id asc"], "queries": [], "artifacts": {},
        }
        for profile in profiles:
            path = staging / f"{profile}.trec"
            with path.open("w", encoding="utf-8", newline="\n") as stream:
                for query in queries:
                    count = 0
                    total = 0
                    for page in range(1, math.ceil(top_k / 100) + 1):
                        result = backend.search(SearchRequest(
                            query=query["query"], profile=profile, page=page, page_size=min(top_k, 100),
                        ))
                        if result.metadata != ready[profile]:
                            raise ValueError("Identità indice cambiata durante l'export")
                        total = result.total
                        for hit in result.hits:
                            if hit.rank > top_k:
                                break
                            if any(c.isspace() for c in hit.document_id):
                                raise ValueError("document_id non rappresentabile in TREC")
                            stream.write(
                                f"{query['query_id']} Q0 {hit.document_id} {hit.rank} "
                                f"{hit.score!r} {profile}-v1\n"
                            )
                            count += 1
                        if count >= min(total, top_k):
                            break
                    manifest["queries"].append({
                        **query, "profile": profile, "total": total, "exported": count,
                    })
            manifest["artifacts"][path.name] = checksum(path)
        if backend.readiness() != ready:
            raise ValueError("Identità indice cambiata durante l'export")
        (staging / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        staging.rename(output)
    return manifest
