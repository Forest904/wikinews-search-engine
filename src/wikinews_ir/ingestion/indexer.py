"""Validated, immutable baseline indices with independently verifiable manifests."""

import json
import platform
import re
import subprocess
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from time import perf_counter

from elasticsearch.helpers import scan, streaming_bulk

from wikinews_ir.ingestion.corpus import ProcessedArticle, checksum
from wikinews_ir.retrieval.profiles import digest, index_config, index_name


def execution():
    def git(*args):
        result = subprocess.run(["git", *args], capture_output=True, text=True, check=False)
        return result.stdout.strip() if result.returncode == 0 else None

    return {
        "timestamp": datetime.now(UTC).isoformat(), "python": platform.python_version(),
        "client_version": version("elasticsearch"),
        "git_commit": git("rev-parse", "HEAD"), "git_dirty": bool(git("status", "--porcelain")),
    }


def articles(path):
    with Path(path).open(encoding="utf-8") as stream:
        for line in stream:
            yield ProcessedArticle.model_validate_json(line).model_dump(mode="json")


def content_signature(items):
    signatures = {}
    for item in items:
        identifier = item["document_id"]
        if not identifier or identifier in signatures:
            raise ValueError("Identificativo vuoto o duplicato")
        signatures[identifier] = digest(item)
    return len(signatures), digest(signatures)


def validate_corpus(directory):
    directory = Path(directory)
    manifest = json.loads((directory / "manifest.json").read_text("utf-8"))
    if manifest.get("valid") is not True or manifest.get("mode") != "build":
        raise ValueError("Manifest corpus non valido")
    for name in ("articles.ndjson", "audit.json", "decisions.ndjson"):
        if checksum(directory / name) != manifest["artifacts"][name]:
            raise ValueError(f"Checksum errato: {name}")
    count, signature = content_signature(articles(directory / "articles.ndjson"))
    if count == 0 or count != manifest["counts"]["articles_produced"]:
        raise ValueError("Conteggio corpus errato o corpus vuoto")
    return {
        "snapshot_id": manifest["snapshot_id"], "pipeline_version": manifest["pipeline_version"],
        "corpus_sha256": manifest["artifacts"]["articles.ndjson"],
        "corpus_manifest_sha256": checksum(directory / "manifest.json"),
        "document_count": count, "content_sha256": signature,
    }


def actual_signature(client, name):
    def sources():
        for hit in scan(client, index=name, query={"query": {"match_all": {}}}):
            if hit["_id"] != hit["_source"]["document_id"]:
                raise ValueError("ID Elasticsearch diverso dal document_id")
            yield hit["_source"]
    return content_signature(sources())


def inspect_index(client, name, profile):
    """Check actual mapping/settings, not just a self-reported configuration hash."""
    response = client.indices.get(index=name)
    if set(response) != {name}:
        raise ValueError("Usare un nome di indice fisico, non un alias")
    actual = response[name]
    meta = actual["mappings"].get("_meta", {})
    expected = index_config(profile)
    mapping = {k: v for k, v in actual["mappings"].items() if k != "_meta"}
    settings = actual["settings"]["index"]
    bm25 = settings.get("similarity", {}).get("default", {})
    if (
        mapping != expected["mappings"]
        or settings["number_of_shards"] != "1"
        or settings["number_of_replicas"] != "0"
        or bm25.get("type") != "BM25"
        or float(bm25.get("k1", 0)) != 1.2 or float(bm25.get("b", 0)) != 0.75
        or meta.get("index_config_sha256") != digest(expected)
        or meta.get("state") != "ready"
        or not all(isinstance(meta.get(key), str) and meta[key] for key in (
            "snapshot_id", "pipeline_version", "corpus_sha256",
            "corpus_manifest_sha256", "content_sha256",
        ))
        or type(meta.get("document_count")) is not int or meta["document_count"] <= 0
        or settings.get("blocks", {}).get("write") != "true"
    ):
        raise ValueError("Indice incompleto o incompatibile: esegui index build --rebuild")
    return {**meta, "index": name, "index_uuid": settings["uuid"]}


def build_indices(backend, directory, profiles=("E0", "E1"), rebuild=False,
                  output=Path("experiments/reports/index-build")):
    identity = validate_corpus(directory)
    names = [index_name(backend.settings, p) for p in profiles]
    if len(set(names)) != len(names) or any(
        not re.fullmatch(r"[a-z0-9][a-z0-9_-]+", n) for n in names
    ):
        raise ValueError("Nomi indice non validi o coincidenti")
    client = backend.client.options(request_timeout=120)
    # Preflight every target before any destructive rebuild.
    for name, profile in zip(names, profiles, strict=True):
        if client.indices.exists_alias(name=name):
            raise ValueError("La destinazione non può essere un alias")
        if client.indices.exists(index=name) and not rebuild:
            meta = inspect_index(client, name, profile)
            if any(meta.get(k) != v for k, v in identity.items()):
                raise ValueError("Corpus diverso: scegliere nuovi indici o --rebuild")
            if actual_signature(client, name) != (
                identity["document_count"], identity["content_sha256"]
            ):
                raise ValueError("Contenuto indice alterato: usare --rebuild")
    reports = []
    for name, profile in zip(names, profiles, strict=True):
        started = perf_counter()
        reused = bool(client.indices.exists(index=name)) and not rebuild
        if not reused:
            if client.indices.exists(index=name):
                client.indices.delete(index=name)
            config = index_config(profile)
            meta = {**identity, "index_config_sha256": digest(config), "state": "building"}
            config["mappings"]["_meta"] = meta
            client.indices.create(index=name, **config)
            actions = (
                {"_index": name, "_id": item["document_id"], "_source": item}
                for item in articles(Path(directory) / "articles.ndjson")
            )
            failures = []
            success = 0
            for ok, item in streaming_bulk(
                client, actions, chunk_size=250, max_retries=3,
                raise_on_error=False, raise_on_exception=True,
            ):
                if ok:
                    success += 1
                else:
                    operation = next(iter(item.values()))
                    failures.append({"document_id": operation.get("_id"),
                                     "status": operation.get("status"),
                                     "error": operation.get("error")})
            if failures or success != identity["document_count"]:
                Path(output).mkdir(parents=True, exist_ok=True)
                (Path(output) / f"{name}-errors.json").write_text(
                    json.dumps(failures, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                raise ValueError(f"Bulk incompleto in {name}: {success} riusciti; indice non pronto")
            client.indices.refresh(index=name)
            if actual_signature(client, name) != (
                identity["document_count"], identity["content_sha256"]
            ):
                raise ValueError(f"Verifica contenuto fallita in {name}")
            client.indices.put_settings(index=name, settings={"index.blocks.write": True})
            client.indices.put_mapping(index=name, _meta={**meta, "state": "ready"})
        metadata = inspect_index(client, name, profile)
        report = {
            **metadata, "profile": profile, "reused": reused,
            "duration_seconds": perf_counter() - started, "execution": execution(),
            "elasticsearch_version": client.info()["version"]["number"], "success": True,
        }
        Path(output).mkdir(parents=True, exist_ok=True)
        destination = Path(output) / f"{name}-{datetime.now(UTC).strftime('%Y%m%dT%H%M%S%f')}.json"
        destination.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        reports.append(report)
    return reports
