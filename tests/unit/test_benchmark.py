import copy
import json
import subprocess
import sys

import httpx
import pytest

from wikinews_ir.adapters.wikimedia import capture, external_run, normalize
from wikinews_ir.evaluation import benchmark as b
from wikinews_ir.evaluation import silver as s
from wikinews_ir.evaluation.artifacts import encoded, file_sha, jsonl, read_rows, write_bundle
from wikinews_ir.evaluation.contracts import Judgment, Topic
from wikinews_ir.ingestion.indexer import validate_corpus


@pytest.fixture
def setup(tmp_path):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    docs = [dict(document_id=str(i), revision_id="10", title=f"Notizia {i}",
                 body=f"Testo sintetico {i}: pioggia a Roma.", url=f"https://example.org/{i}",
                 categories=[], publication_date=None, publication_date_status="missing",
                 publication_date_evidence=[], sources=[], license=[], provenance={})
            for i in range(1, 4)]
    (corpus/"articles.ndjson").write_text(jsonl(docs), encoding="utf-8")
    (corpus/"audit.json").write_text("{}", encoding="utf-8")
    (corpus/"decisions.ndjson").write_text("", encoding="utf-8")
    (corpus/"manifest.json").write_text(encoded({
        "valid": True, "mode": "build", "snapshot_id": "synthetic", "pipeline_version": "1",
        "counts": {"articles_produced": 3}, "artifacts": {
            n: file_sha(corpus/n) for n in ("articles.ndjson", "audit.json", "decisions.ndjson")
        }}), encoding="utf-8")
    topic = dict(query_id="Q1", query="pioggia Roma", information_need="Pioggia a Roma",
                 narrative="Notizie sulla pioggia a Roma", relevance_criteria={
                     "0": "Altro evento", "1": "Informazioni secondarie", "2": "Tema centrale"},
                 exclusion_criteria=["Altre città"], type="topical", theme="meteo",
                 temporal_constraints={}, event_family="rain", split="calibration")
    topics = tmp_path/"topics.jsonl"
    topics.write_text(jsonl([topic]), encoding="utf-8")
    protocol = tmp_path/"protocol.yaml"
    protocol.write_text("version: draft-1\nstatus: draft\nsilver_mode: codex_chat\n", encoding="utf-8")
    runs = tmp_path/"runs"
    runs.mkdir()
    (runs/"E0.trec").write_text("Q1 Q0 1 1 4 E0-v1\nQ1 Q0 2 2 3 E0-v1\n", encoding="utf-8")
    (runs/"E1.trec").write_text("Q1 Q0 2 1 5 E1-v1\nQ1 Q0 3 2 2 E1-v1\n", encoding="utf-8")
    identity = validate_corpus(corpus)
    manifest = {"top_k": 2, "profiles": {p: {**identity, "profile_version": "1"}
                                           for p in ("E0", "E1")},
                "queries": [{"query_id": "Q1", "query": topic["query"], "profile": p,
                             "exported": 2} for p in ("E0", "E1")],
                "artifacts": {n: file_sha(runs/n) for n in ("E0.trec", "E1.trec")}}
    (runs/"manifest.json").write_text(encoded(manifest), encoding="utf-8")
    return dict(root=tmp_path, corpus=corpus, topics=topics, topic=topic,
                protocol=protocol, runs=runs, docs=docs)


def make_packet(setup):
    root = setup["root"]
    b.pool(setup["topics"], setup["corpus"], [setup["runs"]], root/"pool")
    b.select(root/"pool", root/"selection")
    b.packet(setup["topics"], setup["protocol"], root/"selection", setup["corpus"], root/"packet")
    s.prepare(root/"packet", root/"chat", "test-batch")
    return root/"chat"


def judgments(chat):
    data = json.loads((chat/"packet.json").read_text("utf-8"))
    docs = {d["document_id"]: d for d in data["documents"]}
    return [dict(judgment_id=f"J-{p['document_id']}", **p,
                 revision_id=docs[p["document_id"]]["revision_id"],
                 body_sha256=docs[p["document_id"]]["body_sha256"],
                 protocol_version="draft-1", source="codex_chat", annotator_id="codex-chat",
                 judged_at="2026-11-16T15:00:00+01:00", status="judged", grade=2,
                 rationale="Test sintetico", evidence=[{"quote": docs[p["document_id"]]["body"]}])
            for p in data["pairs"]]


def test_end_to_end_and_standalone(setup):
    root = setup["root"]
    b.queries(setup["topics"], setup["protocol"], root/"queries")
    assert read_rows(root/"queries"/"queries.jsonl") == [{"query_id": "Q1", "query": "pioggia Roma"}]
    chat = make_packet(setup)
    data = json.loads((chat/"packet.json").read_text("utf-8"))
    assert all(set(p) == {"query_id", "document_id"} for p in data["pairs"])
    assert "provenance" not in (chat/"packet.json").read_text("utf-8")
    rows = judgments(chat)
    rows[-1].update(status="needs_review", grade=None, evidence=[], ambiguity_reason="Data ignota")
    path = root/"labels.jsonl"
    path.write_text(jsonl(rows), encoding="utf-8")
    result = subprocess.run([sys.executable, "-I", str(chat/"validate.py"), "--packet", str(chat),
                             "--judgments", str(path)], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    report = s.validate_silver(chat, path)
    assert report["judgments"][0]["evidence"][0]["start"] == 0
    s.import_silver(chat, path, root/"import", "reviewer", "session-1")
    s.export_qrels(chat, root/"import", root/"qrels", "silver")
    assert (root/"qrels"/"qrels_silver.tsv").read_text() == "Q1 0 1 2\nQ1 0 2 2\n"
    with pytest.raises(ValueError, match="esiste"):
        s.import_silver(chat, path, root/"import", "reviewer", "session-1")


def test_selection_repeatable_overlap(setup):
    root = setup["root"]
    b.pool(setup["topics"], setup["corpus"], [setup["runs"]], root/"pool")
    quotas = {"E0-v1": 2, "E1-v1": 2}
    for name in ("a", "b"):
        b.select(root/"pool", root/name, quotas, 42)
    assert (root/"a"/"selection.jsonl").read_bytes() == (root/"b"/"selection.jsonl").read_bytes()
    rows = read_rows(root/"a"/"selection.jsonl")
    assert len(rows) == 3
    assert rows[1]["selection"] == ["E0-v1", "E1-v1"]
    with pytest.raises(ValueError, match="Seed"):
        b.select(root/"pool", root/"bad", quotas)


@pytest.mark.parametrize("mutation", ["grade", "citation", "duplicate", "missing", "revision", "id"])
def test_invalid_silver(setup, mutation):
    chat = make_packet(setup)
    rows = judgments(chat)
    if mutation == "grade":
        rows[0]["grade"] = True
    elif mutation == "citation":
        rows[0]["evidence"] = [{"quote": "inesistente"}]
    elif mutation == "duplicate":
        rows.append(rows[0])
    elif mutation == "missing":
        rows.pop()
    elif mutation == "revision":
        rows[0]["revision_id"] = "99"
    else:
        rows[0]["document_id"] = "inventato"
    path = setup["root"]/"bad.jsonl"
    path.write_text(jsonl(rows), encoding="utf-8")
    assert not s.validate_silver(chat, path)["valid"]
    with pytest.raises(ValueError):
        s.import_silver(chat, path, setup["root"]/"badimport", "operator", "execution")
    if mutation == "missing":
        assert s.validate_silver(chat, path, allow_partial=True)["valid"]


def test_input_mutation_detected(setup):
    chat = make_packet(setup)
    (chat/"PROMPT.md").write_text("changed", encoding="utf-8")
    with pytest.raises(ValueError, match="Checksum"):
        s.validate_silver(chat, setup["root"]/"missing.jsonl")


def test_split_and_schema(setup):
    with pytest.raises(ValueError):
        Topic.model_validate({**setup["topic"], "relevance_criteria": {"0": "no"}})
    setup["topics"].write_text(jsonl([setup["topic"], {**setup["topic"], "query_id": "Q2",
                                                    "split": "test"}]), encoding="utf-8")
    with pytest.raises(ValueError, match="Famiglia"):
        b.load_topics(setup["topics"])


@pytest.mark.parametrize("field", ["corpus_sha256", "query"])
def test_incompatible_runs(setup, field):
    path = setup["runs"]/"manifest.json"
    manifest = json.loads(path.read_text())
    if field == "query":
        manifest["queries"][0]["query"] = "different"
    else:
        manifest["profiles"]["E0"][field] = "wrong"
    path.write_text(encoded(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="incompatibil"):
        b.pool(setup["topics"], setup["corpus"], [setup["runs"]], setup["root"]/"pool")


def test_gold_requires_final_resolution(setup):
    chat = make_packet(setup)
    raw = judgments(chat)[:1]
    raw[0].update(source="human", annotator_id="alice", final=False)
    final = {**raw[0], "judgment_id": "final-1", "annotator_id": "charlie", "final": True,
             "origin_judgment_ids": [raw[0]["judgment_id"]]}
    path = setup["root"]/"gold.jsonl"
    path.write_text(jsonl(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="pendente"):
        s.export_qrels(chat, path, setup["root"]/"bad", "gold")
    path.write_text(jsonl([*raw, final]), encoding="utf-8")
    s.export_qrels(chat, path, setup["root"]/"gold", "gold")
    assert (setup["root"]/"gold"/"qrels_gold.tsv").read_text() == "Q1 0 1 2\n"
    with pytest.raises(ValueError):
        Judgment.model_validate({**final, "source": "codex_chat"})


def test_mediawiki_capture_replay_and_pool(setup):
    topics = b.load_topics(setup["topics"])
    requests = []

    def handler(request):
        requests.append(request)
        if len(requests) == 1:
            return httpx.Response(503)
        if "sroffset" not in request.url.params:
            return httpx.Response(200, json={"query": {"search": [
                {"pageid": 1, "ns": 0, "title": "Uno"}]},
                "continue": {"sroffset": 1, "continue": "-||"}})
        return httpx.Response(200, json={"query": {"search": [
            {"pageid": 999, "ns": 0, "title": "Fuori corpus"}]}})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    archive = capture(topics, 2, "test/contact", client, lambda _: None)
    assert len(requests) == 3
    path = setup["root"]/"archive.json"
    path.write_text(encoded(archive), encoding="utf-8")
    output = setup["root"]/"external"
    external_run(setup["topics"], setup["corpus"], output, top_k=2, replay=path)
    rows = read_rows(output/"results.jsonl")
    assert [r["in_corpus"] for r in rows] == [True, False]
    b.pool(setup["topics"], setup["corpus"], [setup["runs"], output], setup["root"]/"pool")
    assert len(read_rows(setup["root"]/"pool"/"pool.jsonl")[0]["provenance"]) == 2
    archive["pages"].pop()
    with pytest.raises(ValueError, match="parziale"):
        normalize(archive, topics, {}, 2)


def test_mediawiki_failures_and_empty(setup):
    topics = b.load_topics(setup["topics"])
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(429)))
    with pytest.raises(httpx.HTTPStatusError):
        capture(topics, 2, "contact", client, lambda _: None)
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(
        200, json={"query": {"search": []}})))
    archive = capture(topics, 2, "contact", client)
    assert normalize(archive, topics, {}, 2) == []
    archive["pages"][0]["response"]["query"]["search"] = [
        {"pageid": 1, "ns": 0, "title": "one"}] * 2
    with pytest.raises(ValueError, match="duplicato"):
        normalize(archive, topics, {}, 2)


def test_reconcile_does_not_import_labels(setup):
    pilot = setup["root"]/"pilot"
    pilot.mkdir()
    topic = copy.deepcopy(setup["topic"])
    topic["topic_id"] = topic.pop("query_id")
    for key in ("theme", "event_family", "split"):
        del topic[key]
    (pilot/"topics.jsonl").write_text(jsonl([topic]), encoding="utf-8")
    (pilot/"documents.jsonl").write_text(jsonl([{"doc_id": 1, "text": "old text"}]), encoding="utf-8")
    (pilot/"candidates.jsonl").write_text(jsonl([
        {"topic_id": "Q1", "doc_id": 1, "version_id": 10},
        {"topic_id": "Q1", "doc_id": 9, "version_id": 10}]), encoding="utf-8")
    result = b.reconcile(pilot, setup["corpus"], setup["root"]/"reconciled")
    assert result["metadata"]["matched_revisions"] == 1
    assert result["metadata"]["labels_imported"] is False
    report = json.loads((setup["root"]/"reconciled"/"report.json").read_text())
    assert not report[0]["text_equal"] and not report[1]["present"]


def test_artifact_no_overwrite(tmp_path):
    write_bundle(tmp_path/"out", "test", {"a.json": "{}"})
    with pytest.raises(ValueError):
        write_bundle(tmp_path/"out", "test", {"a.json": "changed"})
    assert (tmp_path/"out"/"a.json").read_text() == "{}"


def test_ambiguous_unicode_evidence_and_malformed_output(setup):
    from wikinews_ir.evaluation.artifacts import sha

    chat = make_packet(setup)
    data = json.loads((chat/"packet.json").read_text("utf-8"))
    data["documents"][0]["body"] = "🌧 città città"
    data["documents"][0]["body_sha256"] = sha("🌧 città città")
    write_bundle(setup["root"]/"unicode-packet", "packet", {"packet.json": encoded(data)})
    s.prepare(setup["root"]/"unicode-packet", setup["root"]/"unicode-chat", "unicode")
    chat = setup["root"]/"unicode-chat"
    records = judgments(chat)
    records[0]["evidence"] = [{"quote": "città"}]
    output = setup["root"]/"unicode.jsonl"
    output.write_text(jsonl(records), encoding="utf-8")
    assert not s.validate_silver(chat, output)["valid"]
    records[0]["evidence"] = [{"quote": "città", "start": 2, "end": 7}]
    output.write_text(jsonl(records), encoding="utf-8")
    assert s.validate_silver(chat, output)["valid"]
    output.write_text("{broken", encoding="utf-8")
    assert not s.validate_silver(chat, output)["valid"]


def test_test_silver_requires_frozen_protocol(setup):
    chat = make_packet(setup)
    data = json.loads((chat/"packet.json").read_text("utf-8"))
    data["topics"][0]["split"] = "test"
    write_bundle(setup["root"]/"test-packet", "packet", {"packet.json": encoded(data)})
    with pytest.raises(ValueError, match="congelato"):
        s.prepare(setup["root"]/"test-packet", setup["root"]/"test-chat", "test")


def test_cli_validation_success_and_failure(setup):
    result = subprocess.run([sys.executable, "-m", "wikinews_ir.cli", "benchmark", "validate",
                             "--topics", str(setup["topics"]), "--protocol", str(setup["protocol"])],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["valid"] is True
    setup["topics"].write_text("", encoding="utf-8")
    result = subprocess.run([sys.executable, "-m", "wikinews_ir.cli", "benchmark", "validate",
                             "--topics", str(setup["topics"]), "--protocol", str(setup["protocol"])],
                            capture_output=True, text=True)
    assert result.returncode == 1
