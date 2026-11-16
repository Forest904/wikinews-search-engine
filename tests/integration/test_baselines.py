import json

import pytest
from elasticsearch.helpers import scan

from wikinews_ir.evaluation.runs import export_runs
from wikinews_ir.ingestion.corpus import checksum
from wikinews_ir.ingestion.indexer import build_indices
from wikinews_ir.models import SearchRequest
from wikinews_ir.retrieval.engine import RetrievalUnavailable

pytestmark = pytest.mark.integration


def test_baselines_rebuild_ties_analyzers_and_export(seeded_backend, tmp_path):
    backend = seeded_backend
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    items = [hit["_source"] for hit in scan(backend.client, index=backend.settings.elasticsearch_index)]
    for identifier in ("tie-z", "tie-a", "tie-m"):
        items.append({**items[0], "document_id": identifier,
                      "title": "Astronauti", "body": "Astronauti"})
    (corpus / "articles.ndjson").write_text(
        "".join(json.dumps(item) + "\n" for item in items), encoding="utf-8"
    )
    (corpus / "audit.json").write_text("{}", encoding="utf-8")
    (corpus / "decisions.ndjson").write_text("", encoding="utf-8")
    manifest = {"valid": True, "mode": "build", "snapshot_id": "integration",
                "pipeline_version": "fixture-1", "counts": {"articles_produced": len(items)},
                "artifacts": {name: checksum(corpus / name) for name in
                              ("articles.ndjson", "audit.json", "decisions.ndjson")}}
    (corpus / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="Corpus diverso"):
        build_indices(backend, corpus, output=tmp_path / "reports")
    build_indices(backend, corpus, rebuild=True, output=tmp_path / "reports")
    assert backend.search(SearchRequest(query="astronauta", profile="E0")).total == 0
    assert backend.search(SearchRequest(query="astronauta", profile="E1")).total == 3
    hits = [backend.search(SearchRequest(query="astronauti", page=i, page_size=1)).hits[0]
            for i in (1, 2, 3)]
    assert [hit.document_id for hit in hits] == ["tie-a", "tie-m", "tie-z"]
    assert [hit.rank for hit in hits] == [1, 2, 3]
    assert len({hit.score for hit in hits}) == 1
    before = backend.readiness()
    assert all(r["reused"] for r in build_indices(backend, corpus, output=tmp_path / "reports"))
    assert before == backend.readiness()
    queries = tmp_path / "queries.jsonl"
    queries.write_text('{"query_id":"q1","query":"astronauti"}\n', encoding="utf-8")
    first = export_runs(backend, queries, tmp_path / "first")
    build_indices(backend, corpus, rebuild=True, output=tmp_path / "reports")
    second = export_runs(backend, queries, tmp_path / "second")
    assert first["artifacts"] == second["artifacts"]
    assert before["E0"]["index_uuid"] != backend.readiness()["E0"]["index_uuid"]
    name = backend.settings.elasticsearch_index
    backend.client.indices.put_settings(index=name, settings={"index.blocks.write": False})
    with pytest.raises(RetrievalUnavailable, match="incompatibile"):
        backend.search(SearchRequest(query="astronauti"))
    backend.client.update(index=name, id="tie-a", doc={"body": "alterato"}, refresh=True)
    backend.client.indices.put_settings(index=name, settings={"index.blocks.write": True})
    with pytest.raises(ValueError, match="alterato"):
        build_indices(backend, corpus, output=tmp_path / "reports")
