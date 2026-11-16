"""Offline commands (only synthetic demo fixture loading is implemented)."""

import argparse
import json
from pathlib import Path

from elasticsearch.helpers import bulk

from wikinews_ir.config import Settings
from wikinews_ir.models import Article
from wikinews_ir.retrieval.engine import RetrievalEngine

ROOT = Path(__file__).resolve().parents[2]


def seed_demo(settings: Settings | None = None) -> None:
    engine = RetrievalEngine(settings) if settings is not None else RetrievalEngine()
    try:
        settings = engine.settings
        if not engine.check_ready():
            raise RuntimeError("Elasticsearch non disponibile; controlla docker compose ps")
        mapping = json.loads((ROOT / "configs" / "indices" / "standard.json").read_text(encoding="utf-8"))
        with (ROOT / "tests" / "fixtures" / "articles.json").open(encoding="utf-8") as stream:
            articles = [Article.model_validate(item).model_dump() for item in json.load(stream)]
        ids = [item["document_id"] for item in articles]
        if len(ids) != len(set(ids)):
            raise ValueError("Identificativi fixture duplicati")
        if not engine.client.indices.exists(index=settings.elasticsearch_index):
            engine.client.indices.create(index=settings.elasticsearch_index, **mapping)
        actions = [
            {"_index": settings.elasticsearch_index, "_id": item["document_id"], "_source": item}
            for item in articles
        ]
        success, errors = bulk(engine.client, actions, raise_on_error=False, refresh=True)
        if errors:
            raise RuntimeError(f"Errori indicizzazione: {errors[:2]}")
        print(f"Caricati {success} articoli fittizi in {settings.elasticsearch_index}")
    finally:
        engine.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Wikinews IR CLI")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("seed-demo", help="Carica solo le fixture sintetiche")
    args = parser.parse_args()
    if args.command == "seed-demo":
        seed_demo()


if __name__ == "__main__":
    main()
