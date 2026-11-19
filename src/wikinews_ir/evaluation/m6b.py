"""Run the frozen M5 production benchmark from the repository root."""

import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from filelock import FileLock, Timeout

from .artifacts import encoded, file_sha, jsonl, verify_bundle, write_bundle
from .benchmark import load_topics
from .m6b_analysis import PROFILES, analyze, select_candidate
from .report import evaluate
from .report_inputs import load_labels, load_rankings

ROOT = Path("experiments/reports/m6b-production-1.1")
INDEX = Path("benchmarks/v1/manifests/m5-production-1.1.json")
ARCHIVE = Path("output/benchmark-frozen-v1.1/archive")
TOPICS = ARCHIVE / "topics__production-approved.jsonl"
RUNS = [Path("experiments/runs/production-local"), Path("experiments/runs/production-external")]
EXPORT = Path("output/m5d/m5-production-1.1")
VARIANTS = ROOT / "variant-runs"
POLICY = {
    "selection": ["development gold canonical nDCG@10", "P@5", *PROFILES],
    "comparisons": ["E1-E0", "E2-E1", "E3-E2", "E4-E2", "wikimedia reference"],
    "metrics": ["nDCG@10", "P@5 grade >= 1", "MRR@10 event-specific"],
    "subgroups": ["all frozen typos, average within parent", "multi-constraint E4-E2"],
    "coverage": "returned and judged at 5/10; condense available depth 100 before cutoff",
    "judges": "paired grades and ordering on intersection; report full silver separately",
    "errors": "lowest and highest gold nDCG difference per contrast; lowest query ID breaks ties",
}


def read(path):
    return json.loads(path.read_text("utf-8"))


def check(path, digest):
    if file_sha(path) != digest:
        raise ValueError(f"Checksum incompatibile: {path}")


def identities():
    paths = [
        INDEX,
        Path("uv.lock"),
        Path("pyproject.toml"),
        *sorted(Path("src/wikinews_ir").rglob("*.py")),
        *sorted(Path("configs/retrieval").glob("*.yaml")),
        *sorted(Path("src/wikinews_ir/resources").rglob("*.yaml")),
    ]
    return {p.as_posix(): file_sha(p) for p in paths}


def inputs():
    pins = read(INDEX)["sha256"]
    check(ARCHIVE / "manifest.json", pins[(ARCHIVE / "manifest.json").as_posix()])
    hashes = read(ARCHIVE / "manifest.json")["artifacts"]
    check(TOPICS, hashes[TOPICS.name])
    for directory, prefix in zip(RUNS, ("local_run__", "external_run__"), strict=True):
        frozen = ARCHIVE / (prefix + "manifest.json")
        check(frozen, hashes[frozen.name])
        if read(directory / "manifest.json") != read(frozen):
            raise ValueError(f"Manifest diverso dal congelamento: {directory}")
    local, external = [verify_bundle(p) for p in RUNS]
    meta = external["metadata"]
    if (
        local["top_k"] != meta["top_k"]
        or local["top_k"] != 100
        or set(local["profiles"]) != {r.split("-")[0] for r in PROFILES}
        or any(
            profile[k] != v
            for profile in local["profiles"].values()
            for k, v in meta["corpus"].items()
        )
    ):
        raise ValueError("Corpus, profondità o profili incompatibili")
    return load_topics(TOPICS), local


def variant_queries(topics):
    return [
        dict(query_id=f"{t['query_id']}-{i}", query=query)
        for t in topics
        for i, query in enumerate(t["variants"], 1)
    ]


def variant_runs(queries, local):
    if not VARIANTS.exists():
        from wikinews_ir.retrieval.engine import RetrievalEngine

        from .runs import export_runs

        backend = RetrievalEngine()
        try:
            with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
                path = Path(tmp) / "variants.jsonl"
                path.write_text(jsonl(queries), encoding="utf-8")
                export_runs(backend, path, VARIANTS, local["top_k"], ("E2", "E3"))
        finally:
            backend.close()
    manifest = verify_bundle(VARIANTS)
    if (
        manifest["profiles"] != {r: local["profiles"][r] for r in ("E2", "E3")}
        or manifest["top_k"] != local["top_k"]
        or manifest["elasticsearch_version"] != local["elasticsearch_version"]
    ):
        raise ValueError("Identità dei ranking supplementari incompatibile")
    return dict(load_rankings(VARIANTS, queries))


def run_split(split, topics, variants, destination):
    selected = {t["query_id"]: t for t in topics if t["split"] == split}
    ids = {t["query_id"] for t in topics}
    index = read(INDEX)
    pins = index["sha256"]
    gold = EXPORT / "gold" / split
    silver = EXPORT / "silver/qrels"
    for directory in (gold, silver):
        path = directory / "manifest.json"
        check(path, pins[path.as_posix()])
    # The production silver export combines splits. Project IDs before parsing any grade.
    verify_bundle(silver, "qrels")
    lines = [
        line
        for line in (silver / "qrels_silver.tsv").read_text("utf-8").splitlines()
        if line.split(maxsplit=1)[0] in selected
    ]
    with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
        result = Path(tmp) / "result"
        result.mkdir()
        projection = result / "silver"
        write_bundle(
            projection,
            "qrels",
            {"qrels_silver.tsv": "\n".join(lines) + "\n"},
            dict(
                source="silver",
                abstentions=0,
                split=split,
                origin=file_sha(silver / "manifest.json"),
            ),
        )
        evaluate(TOPICS, split, RUNS, result / "canonical", gold, projection)
        labels = {
            name: load_labels(p, name, ids, selected, split)[0]
            for name, p in [("gold", gold), ("silver", projection)]
        }
        expected = index["coverage"][split]
        if (
            any(len(labels[s]) != expected[s] for s in labels)
            or len(labels["gold"].keys() & labels["silver"].keys()) != expected["shared"]
            or len(selected) != {"development": 24, "test": 16}[split]
        ):
            raise ValueError("Copertura diversa da M5-D")
        runs = dict(item for directory in RUNS for item in load_rankings(directory, topics))
        files, summary = analyze(selected, runs, labels, variants)
        # Store the stable projection path in the canonical manifest.
        manifest = result / "canonical/manifest.json"
        data = read(manifest)
        data["metadata"]["sources"]["silver"]["path"] = str(destination / "silver")
        manifest.write_text(encoded(data), encoding="utf-8")
        write_bundle(
            result / "analysis",
            "m6b-analysis",
            files,
            dict(
                gold=summary,
                code_and_inputs=identities(),
                variant_manifest=file_sha(VARIANTS / "manifest.json"),
            ),
        )
        result.rename(destination)


def evidence(directory):
    result = {}
    for name in ("silver", "canonical", "analysis"):
        path = directory / name
        verify_bundle(path)
        result[name] = file_sha(path / "manifest.json")
    return result


def experiment(phase):
    ROOT.mkdir(parents=True, exist_ok=True)
    try:
        with FileLock(str(ROOT / "experiment.lock"), timeout=0):
            return _experiment(phase)
    except Timeout as exc:
        raise ValueError("Esperimento già in corso") from exc


def _experiment(phase):
    topics, local = inputs()
    dev, freeze, final = [ROOT / name for name in ("development", "freeze", "final")]
    queries = variant_queries(topics)
    if phase == "development":
        if not dev.exists():
            run_split("development", topics, variant_runs(queries, local), dev)
        return evidence(dev)
    if not dev.exists() or not VARIANTS.exists():
        raise ValueError("Development incompleto")
    receipts = evidence(dev)
    variant_manifest = verify_bundle(VARIANTS)
    development = read(dev / "analysis/manifest.json")["metadata"]
    if development["code_and_inputs"] != identities() or development[
        "variant_manifest"
    ] != file_sha(VARIANTS / "manifest.json"):
        raise ValueError("Development generato con codice o varianti differenti")
    scores = development["gold"]
    spec = dict(
        candidate=select_candidate(scores),
        policy=POLICY,
        development=receipts,
        code_and_inputs=identities(),
        variant_manifest=file_sha(VARIANTS / "manifest.json"),
        variant_runs=variant_manifest["artifacts"],
        m5d=read(INDEX)["sha256"],
        topics=file_sha(TOPICS),
        runs=[file_sha(p / "manifest.json") for p in RUNS],
    )
    if phase == "freeze" and not freeze.exists():
        write_bundle(freeze, "m6b-freeze", {"protocol.json": encoded(spec)})
    if not freeze.exists():
        raise ValueError("Congelamento richiesto prima del test")
    verify_bundle(freeze, "m6b-freeze")
    if read(freeze / "protocol.json") != spec:
        raise ValueError("Il protocollo congelato non corrisponde agli input correnti")
    if phase == "freeze":
        return {"candidate": spec["candidate"], "freeze": file_sha(freeze / "protocol.json")}
    ledger = ROOT / "final-attempts.jsonl"
    digest = file_sha(freeze / "protocol.json")
    entries = (
        [json.loads(line) for line in ledger.read_text().splitlines()] if ledger.exists() else []
    )
    if any(entry["freeze"] != digest for entry in entries):
        raise ValueError("Registro associato a un altro congelamento")

    def record(event, **fields):
        entries.append(
            dict(event=event, freeze=digest, time=datetime.now(UTC).isoformat(), **fields)
        )
        staging = ledger.with_suffix(".tmp")
        staging.write_text(jsonl(entries), encoding="utf-8")
        staging.replace(ledger)

    if entries and entries[-1]["event"] == "complete":
        if evidence(final) != entries[-1]["result"]:
            raise ValueError("Risultato finale alterato")
        return entries[-1]
    record("resume" if entries else "start")
    if not final.exists():
        run_split("test", topics, variant_runs(queries, local), final)
    result = evidence(final)
    record("complete", result=result)
    return dict(candidate=spec["candidate"], result=result)
