"""Offline demo and corpus preparation commands."""

import argparse
import json
from pathlib import Path

from wikinews_ir.config import Settings
from wikinews_ir.models import Article
from wikinews_ir.retrieval.engine import RetrievalEngine

ROOT = Path(__file__).resolve().parents[2]


def seed_demo(settings: Settings | None = None) -> None:
    from dataclasses import replace
    from tempfile import TemporaryDirectory

    from wikinews_ir.config import get_settings
    from wikinews_ir.ingestion.corpus import checksum
    from wikinews_ir.ingestion.indexer import build_indices

    settings = settings or replace(
        get_settings(), elasticsearch_index="wikinews_demo_standard_v1",
        elasticsearch_italian_index="wikinews_demo_italian_v1",
    )
    backend = RetrievalEngine(settings)
    try:
        if not backend.check_ready():
            raise RuntimeError("Elasticsearch non disponibile; controlla docker compose ps")
        raw = json.loads((ROOT / "tests/fixtures/articles.json").read_text("utf-8"))
        items = [Article.model_validate(item).model_dump() for item in raw]
        if len({item["document_id"] for item in items}) != len(items):
            raise ValueError("Identificativi fixture duplicati")
        with TemporaryDirectory() as temporary:
            corpus = Path(temporary)
            for item in items:
                item.update(revision_id="1", categories=[], publication_date=None,
                            publication_date_status="missing", publication_date_evidence=[],
                            sources=[], license=[], provenance={"fixture": True})
            (corpus / "articles.ndjson").write_text(
                "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in items), encoding="utf-8"
            )
            (corpus / "audit.json").write_text("{}", encoding="utf-8")
            (corpus / "decisions.ndjson").write_text("", encoding="utf-8")
            manifest = {
                "valid": True, "mode": "build", "snapshot_id": "synthetic-m3",
                "pipeline_version": "fixture-1", "counts": {"articles_produced": len(items)},
                "artifacts": {name: checksum(corpus / name) for name in
                              ("articles.ndjson", "audit.json", "decisions.ndjson")},
            }
            (corpus / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            build_indices(backend, corpus, output=corpus / "reports")
        print(f"Fixture pronte: {settings.elasticsearch_index}, {settings.elasticsearch_italian_index}")
    finally:
        backend.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Wikinews IR CLI")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("seed-demo", help="Carica solo le fixture sintetiche")
    corpus = sub.add_parser("corpus", help="Audit e preprocessing offline del dump")
    commands = corpus.add_subparsers(dest="corpus_command", required=True)
    prepare = commands.add_parser(
        "prepare", help="Scarica, verifica e prepara lo snapshot assegnato"
    )
    prepare.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    prepare.add_argument("--output", type=Path, default=Path("data/processed/m2-v1"))
    for name in ("audit", "build"):
        command = commands.add_parser(name)
        command.add_argument("--input", type=Path, required=True)
        command.add_argument("--output", type=Path, required=True)
    index = sub.add_parser("index", help="Indici baseline del corpus processed")
    index_commands = index.add_subparsers(dest="index_command", required=True)
    build = index_commands.add_parser("build")
    build.add_argument("--corpus", type=Path, default=Path("data/processed/m2-v1"))
    build.add_argument("--rebuild", action="store_true")
    build.add_argument("--output", type=Path, default=Path("experiments/reports/index-build"))
    runs = sub.add_parser("runs", help="Esportazione ranking riproducibili")
    run_commands = runs.add_subparsers(dest="run_command", required=True)
    export = run_commands.add_parser("export")
    export.add_argument("--queries", type=Path, required=True)
    export.add_argument("--output", type=Path, required=True)
    export.add_argument("--top-k", type=int, default=100)
    from wikinews_ir.retrieval.profiles import SUPPORTED_PROFILES
    export.add_argument("--profiles", nargs="+", choices=SUPPORTED_PROFILES, default=SUPPORTED_PROFILES)
    args = parser.parse_args()
    if args.command in {"index", "runs"}:
        from elasticsearch.exceptions import ApiError, TransportError

        from wikinews_ir.evaluation.runs import export_runs
        from wikinews_ir.ingestion.indexer import build_indices
        from wikinews_ir.retrieval.engine import RetrievalUnavailable, SearchIndexMissing

        backend = RetrievalEngine()
        try:
            if args.command == "index":
                result = build_indices(backend, args.corpus, rebuild=args.rebuild, output=args.output)
            else:
                result = export_runs(backend, args.queries, args.output, args.top_k, args.profiles)
            print(json.dumps(result, ensure_ascii=False, indent=2))
        except (ValueError, OSError, KeyError, TypeError, RetrievalUnavailable,
                SearchIndexMissing, ApiError, TransportError) as exc:
            if isinstance(exc, (ApiError, TransportError)):
                message = "Elasticsearch non disponibile o operazione rifiutata"
            else:
                message = str(exc)
            parser.exit(1, f"{args.command}: {message}\n")
        finally:
            backend.close()
        return
    if args.command == "seed-demo":
        seed_demo()
    elif args.command == "corpus":
        from wikinews_ir.ingestion.corpus import run_corpus

        try:
            if args.corpus_command == "prepare":
                from wikinews_ir.ingestion.acquisition import prepare

                manifest = prepare(args.raw_dir, args.output)
            else:
                manifest = run_corpus(
                    args.input, args.output, audit_only=args.corpus_command == "audit"
                )
        except (ValueError, OSError) as exc:
            parser.exit(1, f"Corpus: {exc}\n")
        print(json.dumps(manifest["counts"], ensure_ascii=False, indent=2))
        if not manifest["valid"]:
            parser.exit(1, "Audit completato con errori; consultare decisions.ndjson\n")


if __name__ == "__main__":
    main()
