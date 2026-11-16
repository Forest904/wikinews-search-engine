import json

import pytest
from elasticsearch.helpers import scan

from wikinews_ir.ingestion.corpus import checksum
from wikinews_ir.ingestion.indexer import build_indices
from wikinews_ir.models import SearchRequest
from wikinews_ir.retrieval.profiles import SUPPORTED_PROFILES

pytestmark = pytest.mark.integration


def test_advanced_retrieval_on_controlled_corpus(seeded_backend, tmp_path):
    backend = seeded_backend
    base = next(scan(backend.client, index=backend.settings.elasticsearch_index))["_source"]
    texts = {
        "title": ("Energia solare", "Italia pannelli nuovi"),
        "body": ("Italia pannelli nuovi", "Energia solare"),
        "reverse": ("Solare energia", "Italia pannelli nuovi"),
        "gap": ("Energia pulita solare", "Italia pannelli nuovi"),
        "foreign": ("Energia solare", "Francia pannelli nuovi"),
        "cross": ("Energia", "Solare Italia pannelli nuovi"),
        "exact": ("Terremoto", "Soccorsi"),
        "near": ("Terremoti", "Soccorsi"),
        "short": ("Re", "Sovrano"),
        "hostile": ('<script>alert(1)</script> energia', 'Energia & <img src=x onerror=alert(1)>'),
    }
    items = [{**base, "document_id": key, "title": title, "body": body}
             for key, (title, body) in texts.items()]
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "articles.ndjson").write_text(''.join(json.dumps(i) + "\n" for i in items))
    (corpus / "audit.json").write_text("{}")
    (corpus / "decisions.ndjson").write_text("")
    (corpus / "manifest.json").write_text(json.dumps({
        "valid": True, "mode": "build", "snapshot_id": "m4-fixture", "pipeline_version": "1",
        "counts": {"articles_produced": len(items)},
        "artifacts": {n: checksum(corpus / n) for n in ("articles.ndjson", "audit.json", "decisions.ndjson")},
    }))
    reports = build_indices(backend, corpus, profiles=SUPPORTED_PROFILES, rebuild=True,
                            output=tmp_path / "reports")
    assert len(reports) == 2
    assert len({m["index_uuid"] for m in backend.readiness().values()}) == 2

    def search(query, profile="E4"):
        return backend.search(SearchRequest(query=query, profile=profile, page_size=100))

    def ids(query, profile="E4"):
        return {hit.document_id for hit in search(query, profile).hits}

    assert ids('"energia solare"') == {"title", "body", "foreign"}
    assert ids('"energia solare" Italia') == {"title", "body"}
    assert ids('"energia solare" Italia Francia') == {"title", "body", "foreign"}
    assert ids('"energia solare" "pannelli nuovi" Italia') == {"title", "body"}
    assert not ids('"di e il"')
    assert not ids('"energia solare" di il')
    assert ids("energia solare", "E4") == ids("energia solare", "E2")
    ranks = [h.document_id for h in search('"energia solare"').hits]
    assert ranks.index("title") < ranks.index("body")
    assert not ids("terremmoto", "E2")
    assert ids("terremmoto", "E3") == {"exact", "near"}
    assert not ids("ra", "E3")
    assert not ids("di e il", "E3")
    hit = next(h for h in search("energia", "E2").hits if h.document_id == "hostile")
    assert any(s.highlighted for s in hit.title_segments)
    assert '<script>' in ''.join(s.text for s in hit.title_segments)
    assert any(s.highlighted for s in hit.snippet_segments)
    # Highlight is presentation-only, including scores and ordering.
    from wikinews_ir.retrieval.query_builder import build_query
    raw = backend.client.search(index=backend.settings.elasticsearch_italian_index,
        query=build_query("energia", "E2"), size=100,
        sort=[{"_score": "desc"}, {"document_id": "asc"}])
    assert [(h.document_id, h.score) for h in search("energia", "E2").hits] == [
        (h["_id"], h["_score"]) for h in raw["hits"]["hits"]]
