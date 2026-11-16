import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from wikinews_ir.evaluation.runs import export_runs, load_queries
from wikinews_ir.ingestion.corpus import checksum
from wikinews_ir.ingestion.indexer import build_indices, content_signature, validate_corpus
from wikinews_ir.models import SearchHit, SearchRequest, SearchResponse
from wikinews_ir.retrieval.profiles import CONFIGS, index_config, profile_config


@pytest.fixture
def corpus_dir(tmp_path):
    directory = tmp_path / "corpus"
    directory.mkdir()
    item = dict(document_id="1", revision_id="2", title="Titolo", body="Testo",
                url="https://example.org", categories=[], publication_date=None,
                publication_date_status="missing", publication_date_evidence=[],
                sources=[], license=[], provenance={})
    (directory / "articles.ndjson").write_text(json.dumps(item) + "\n", encoding="utf-8")
    (directory / "audit.json").write_text("{}", encoding="utf-8")
    (directory / "decisions.ndjson").write_text("", encoding="utf-8")
    manifest = dict(valid=True, mode="build", snapshot_id="test", pipeline_version="1",
                    counts={"articles_produced": 1}, artifacts={
                        name: checksum(directory / name) for name in
                        ("articles.ndjson", "audit.json", "decisions.ndjson")})
    (directory / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return directory


def test_packaged_configs_match_repository():
    for kind in ("indices", "retrieval"):
        for file in (CONFIGS / kind).iterdir():
            assert file.read_bytes() == (Path("configs") / kind / file.name).read_bytes()
    assert index_config("E0")["mappings"]["properties"]["body"]["analyzer"] == "standard"
    assert index_config("E1")["mappings"]["properties"]["body"]["analyzer"] == "italian"
    assert profile_config("E0")["fields"] == profile_config("E1")["fields"]


def test_corpus_checks_before_backend_writes(corpus_dir):
    assert validate_corpus(corpus_dir)["document_count"] == 1
    (corpus_dir / "articles.ndjson").write_text("bad", encoding="utf-8")
    backend = Mock()
    with pytest.raises(ValueError, match="Checksum"):
        build_indices(backend, corpus_dir, rebuild=True)
    backend.client.options.assert_not_called()


def test_duplicate_ids_and_order_independent_signature():
    a, b = {"document_id": "a", "body": "a"}, {"document_id": "b", "body": "b"}
    assert content_signature([a, b]) == content_signature([b, a])
    with pytest.raises(ValueError, match="duplicato"):
        content_signature([a, a])


@pytest.mark.parametrize("kwargs", [dict(page=0), dict(page_size=101),
                                   dict(page=101, page_size=100), dict(limit=10),
                                   dict(profile="bm25")])
def test_new_request_contract(kwargs):
    with pytest.raises(ValueError):
        SearchRequest(query="x", **kwargs)


@pytest.mark.parametrize("rows", [[], [{"query_id": "a b", "query": "x"}],
                                  [{"query_id": "a", "query": " "}],
                                  [{"query_id": "a", "query": "x"}] * 2])
def test_invalid_query_files(tmp_path, rows):
    path = tmp_path / "queries.jsonl"
    path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
    with pytest.raises(ValueError):
        load_queries(path)


def test_export_pagination_zero_hits_and_atomic_failure(tmp_path):
    path = tmp_path / "queries.jsonl"
    path.write_text('{"query_id":"q1","query":"test"}\n'
                    '{"query_id":"q2","query":"empty"}\n', encoding="utf-8")
    backend = Mock()
    backend.readiness.return_value = {p: {"index_uuid": p} for p in ("E0", "E1")}
    backend.client.info.return_value = {"version": {"number": "test"}}

    def search(request):
        ranks = range((request.page - 1) * request.page_size + 1,
                      min(request.page * request.page_size, 103) + 1)
        return SearchResponse(query=request.query, profile=request.profile, index="test",
                              metadata={"index_uuid": request.profile}, elapsed_ms=0,
                              total=103 if request.query == "test" else 0,
                              hits=[SearchHit(document_id=str(i), rank=i, score=1.0,
                                              title="test", url="") for i in ranks]
                              if request.query == "test" else [])
    backend.search.side_effect = search
    first = export_runs(backend, path, tmp_path / "first", top_k=101)
    second = export_runs(backend, path, tmp_path / "second", top_k=101)
    assert first["artifacts"] == second["artifacts"]
    assert first["queries"][1]["exported"] == 0
    lines = (tmp_path / "first/E0.trec").read_text().splitlines()
    assert len(lines) == 101
    assert lines[-1] == "q1 Q0 101 101 1.0 E0-v1"
    with pytest.raises(ValueError, match="esiste"):
        export_runs(backend, path, tmp_path / "first")
    backend.search.side_effect = RuntimeError("interrupted")
    with pytest.raises(RuntimeError):
        export_runs(backend, path, tmp_path / "failed")
    assert not (tmp_path / "failed").exists()


def test_bulk_error_never_marks_index_ready(corpus_dir, monkeypatch, tmp_path):
    from wikinews_ir.config import Settings

    backend = Mock(settings=Settings())
    client = backend.client.options.return_value
    client.indices.exists.return_value = False
    client.indices.exists_alias.return_value = False
    monkeypatch.setattr("wikinews_ir.ingestion.indexer.streaming_bulk", lambda *a, **kw: iter([
        (False, {"index": {"_id": "1", "status": 400, "error": {"type": "test"}}}),
    ]))
    with pytest.raises(ValueError, match="Bulk incompleto"):
        build_indices(backend, corpus_dir, output=tmp_path / "report")
    client.indices.put_mapping.assert_not_called()
    assert json.loads(next((tmp_path / "report").glob("*-errors.json")).read_text())[0]["document_id"] == "1"
