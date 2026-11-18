import json
from copy import deepcopy
from pathlib import Path

import pytest

from wikinews_ir.annotation_cli import demo_payload
from wikinews_ir.evaluation.artifacts import encoded, file_sha, jsonl, write_bundle
from wikinews_ir.evaluation.pilot import budget, freeze, pilot_report, stats
from wikinews_ir.evaluation.silver import prepare


def read(path):
    return json.loads(path.read_text("utf-8"))


def pilot_export(root, missing=False):
    payload = demo_payload()
    payload["documents"] += [dict(payload["documents"][0], document_id=f"demo-{i}") for i in (5, 6)]
    topic = payload["topics"][0]
    types = ["event-specific", "topical", "entity-oriented", "multi-constraint"]
    payload["topics"] = [dict(topic, query_id=f"P{i}", event_family=f"cal-{i}", type=typ)
                         for i, typ in enumerate(types)]
    payload["pairs"] = [{"query_id": t["query_id"], "document_id": d["document_id"]}
                        for t in payload["topics"] for d in payload["documents"]]
    assignments = [{**p, "user_id": u} for p in payload["pairs"] for u in ("a", "b", "c")]
    history = [{**a, "version": 1, "status": "judged", "grade": 2} for a in assignments]
    timing = [{**a, "phase": phase, "seconds": seconds, "complete": 1}
              for a in assignments for phase, seconds in (("reading", 90), ("annotation", 30))]
    if missing:
        timing.pop()
    write_bundle(root, "annotation-gold-export", {
        "packet.json": encoded(payload), "assignments.jsonl": jsonl(assignments),
        "history.jsonl": jsonl(history), "timing.jsonl": jsonl(timing),
        "source_manifest.json": encoded({"metadata": {"fixture": True}}),
        "discussions.jsonl": jsonl([{"minutes": 10, "participants": '["a","b","c"]',
                                    "notes": "Fixture, rubriche discusse."}])})


def test_measured_report_and_budget(tmp_path):
    pilot_export(tmp_path / "source")
    pilot_report(tmp_path / "source", tmp_path / "report")
    result = read(tmp_path / "report/report.json")
    assert result["ready_for_freeze"] and result["fixture"]
    assert result["completed"] == 72 and result["distinct_pairs"] == 24
    assert result["annotation_seconds"] == {"n": 72, "median": 120, "p75": 120}
    assert result["consumed_person_seconds"] == 72 * 120 + 1800
    assert result["agreement"]["a/b"] == {"graded_pairs": 24, "agreements": 24, "disagreements": 0}
    plan = {"distinct_pairs": 120, "double_pairs": 30, "review_reserve_minutes": 60,
            "annotations_per_user": {"a": 50, "b": 50, "c": 50}}
    (tmp_path / "plan.json").write_text(encoded(plan), "utf-8")
    budget(tmp_path / "report", tmp_path / "plan.json", tmp_path / "budget")
    estimate = read(tmp_path / "budget/budget.json")
    assert estimate["required_person_hours"] == pytest.approx(8.9)
    assert all(s["fits"] for s in estimate["scenarios"])
    assert stats([1, 2, 3, 100]) == {"n": 4, "median": 2.5, "p75": 3}


def test_missing_timing_blocks_budget(tmp_path):
    pilot_export(tmp_path / "source", missing=True)
    pilot_report(tmp_path / "source", tmp_path / "report")
    assert not read(tmp_path / "report/report.json")["ready_for_freeze"]
    (tmp_path / "plan.json").write_text("{}", "utf-8")
    with pytest.raises(ValueError, match="Misure complete"):
        budget(tmp_path / "report", tmp_path / "plan.json", tmp_path / "budget")


def test_estimated_pilot_requires_documented_decisions(tmp_path):
    source = tmp_path / "source"
    pilot_export(source)
    history = [json.loads(line) for line in (source / "history.jsonl").read_text().splitlines()]
    history[0]["grade"] = 1
    files = {p.name: p.read_text("utf-8") for p in source.iterdir() if p.name != "manifest.json"}
    files.update({"history.jsonl": jsonl(history), "discussions.jsonl": "", "timing.jsonl": ""})
    export = tmp_path / "untimed"
    write_bundle(export, "annotation-gold-export", files)
    review_path = tmp_path / "review.json"
    review = {"seconds_per_reading": 120, "source_manifest_sha256": file_sha(export / "manifest.json"),
              "provenance": "Stima dei partecipanti", "decisions": []}
    review_path.write_text(encoded(review), "utf-8")
    with pytest.raises(ValueError, match="disaccordi"):
        pilot_report(export, tmp_path / "report", review_path)
    review["decisions"] = [{k: history[0][k] for k in ("query_id", "document_id", "grade")}
                           | {"rationale": "Informazione secondaria"}]
    review_path.write_text(encoded(review), "utf-8")
    pilot_report(export, tmp_path / "report", review_path)
    result = read(tmp_path / "report/report.json")
    assert result["ready_for_freeze"] and result["annotation_seconds"]["p75"] is None
    assert len(result["missing_timing"]) == 72 and result["consumed_person_seconds"] == 0
    plan = {"distinct_pairs": 190, "double_pairs": 38, "review_reserve_minutes": 120,
            "annotations_per_user": {"a": 76, "b": 76, "c": 76}}
    (tmp_path / "plan.json").write_text(encoded(plan), "utf-8")
    budget(tmp_path / "report", tmp_path / "plan.json", tmp_path / "budget")
    estimate = read(tmp_path / "budget/budget.json")
    assert estimate["sensitivity_hours"] == {"90": 10.1, "120": 12, "150": 13.9}
    assert estimate["total_hours_per_user"] == {"a": 4, "b": 4, "c": 4}
    review["provenance"] = ""
    review_path.write_text(encoded(review), "utf-8")
    with pytest.raises(ValueError, match="provenienza"):
        pilot_report(export, tmp_path / "invalid", review_path)


def freeze_fixture(root):
    # Synthetic artifacts exercise the freeze mechanics; never evidence for the actual milestone.
    report = {"ready_for_freeze": True, "fixture": False, "calibration_families": ["cal-0"]}
    write_bundle(root / "pilot", "pilot-report", {"report.json": encoded(report)})
    topics = [json.loads(line) for line in Path("benchmarks/topics/production-draft.jsonl").read_text("utf-8").splitlines()]
    (root / "topics.jsonl").write_text(jsonl(topics), "utf-8")
    cal = dict(topics[0], query_id="P0", event_family="cal-0", split="calibration")
    (root / "cal.jsonl").write_text(jsonl([cal]), "utf-8")
    doc = demo_payload()["documents"][0]
    pairs = [{"query_id": t["query_id"], "document_id": doc["document_id"]} for t in topics]
    assignments = [{**p, "user_id": ("a", "b", "c")[i % 3]} for i, p in enumerate(pairs)]
    (root / "assignments.jsonl").write_text(jsonl(assignments), "utf-8")
    estimate = {"pilot_manifest_sha256": file_sha(root / "pilot/manifest.json"),
                "scenarios": [{"hours": 12, "fits": True}], "plan": {"distinct_pairs": 40,
                "double_pairs": 0, "annotations_per_user": {"a": 14, "b": 13, "c": 13}}}
    write_bundle(root / "budget", "pilot-budget", {"budget.json": encoded(estimate)})
    queries = {t["query_id"]: t["query"] for t in topics}
    write_bundle(root / "local", "local-test", {})
    manifest = read(root / "local/manifest.json")
    manifest.update(profiles={f"E{i}": {} for i in range(5)}, top_k=20,
                    queries=[{"query_id": q, "query": text, "profile": f"E{i}"}
                             for q, text in queries.items() for i in range(5)])
    (root / "local/manifest.json").write_text(encoded(manifest), "utf-8")
    write_bundle(root / "external", "external-run", {},
                 {"corpus": {}, "queries": queries, "top_k": 20, "complete": True})
    rows = [{**p, "revision_id": doc["revision_id"], "body_sha256": doc["body_sha256"]} for p in pairs]
    write_bundle(root / "pool", "pool", {"pool.jsonl": jsonl(rows)}, {
        "corpus": {}, "run_ids": [f"E{i}-v1" for i in range(5)] + ["wikimedia"],
        "topics_sha256": file_sha(root / "topics.jsonl"), "inputs": {
            "local": file_sha(root / "local/manifest.json"),
            "external": file_sha(root / "external/manifest.json")}})
    quotas = dict.fromkeys([f"E{i}-v1" for i in range(5)] + ["wikimedia"], 2)
    write_bundle(root / "selection", "selection", {"selection.jsonl": jsonl(rows)}, {
        "pool_manifest_sha256": file_sha(root / "pool/manifest.json"), "quotas": quotas, "seed": 42})
    packet = {"protocol": demo_payload()["protocol"], "topics": topics,
              "documents": [doc], "pairs": pairs}
    write_bundle(root / "packet", "packet", {"packet.json": encoded(packet)}, {
        "corpus": {}, "selection_manifest_sha256": file_sha(root / "selection/manifest.json")})
    (root / "prompt.md").write_text("Prompt calibrato di test.", "utf-8")
    plan = {"version": "fixture-frozen", "pilot": "pilot", "budget": "budget", "topics": "topics.jsonl",
            "calibration_topics": "cal.jsonl", "packet": "packet", "pool": "pool", "selection": "selection",
            "local_run": "local", "external_run": "external", "assignments": "assignments.jsonl",
            "prompt": "prompt.md", "model": "unknown", "top_k": 20, "quotas": quotas,
            "seed": 42, "hours": 12, "semantic_overlap_review": "Fixture di collaudo."}
    (root / "freeze.json").write_text(encoded(plan), "utf-8")
    return plan


def test_freeze_chain_and_blind_silver_prompt(tmp_path):
    plan = freeze_fixture(tmp_path)
    freeze(tmp_path / "freeze.json", tmp_path / "frozen")
    packet = read(tmp_path / "frozen/packet/packet.json")
    assert packet["protocol"]["status"] == "frozen"
    assert set(p.name for p in (tmp_path / "frozen/packet").iterdir()) == {
        "packet.json", "PROMPT.md", "manifest.json"}
    prepare(tmp_path / "frozen/packet", tmp_path / "silver", "fixture")
    assert (tmp_path / "silver/PROMPT.md").read_text("utf-8") == "Prompt calibrato di test."
    from wikinews_ir.annotation import connect, create_user
    from wikinews_ir.annotation_workflow import create_block
    from wikinews_ir.pilot import activate_freeze
    with connect(tmp_path / "annotations.sqlite3") as db:
        for user in ("a", "b", "c"):
            create_user(db, user, "password-test", coordinator=user == "a")
        result = activate_freeze(db, "a", tmp_path / "frozen")
        assert result["assignments"] == 40 and not result["already_active"]
        assert activate_freeze(db, "a", tmp_path / "frozen")["already_active"]
        with pytest.raises(ValueError, match="activate-freeze"):
            create_block(db, "a", result["packet_id"], "Q01", "a", None, 0, "42")
    with pytest.raises(ValueError, match="esistente"):
        freeze(tmp_path / "freeze.json", tmp_path / "frozen")
    bad = deepcopy(plan)
    bad["top_k"] = 10
    (tmp_path / "bad.json").write_text(encoded(bad), "utf-8")
    with pytest.raises(ValueError, match="Run esterna"):
        freeze(tmp_path / "bad.json", tmp_path / "invalid")
    assert not (tmp_path / "invalid").exists()


def test_freeze_rejects_fixture_pilot(tmp_path):
    freeze_fixture(tmp_path)
    # Recreate a consistent budget reference after changing the pilot evidence.
    path = tmp_path / "pilot/report.json"
    report = read(path)
    report["fixture"] = True
    path.write_text(encoded(report), "utf-8")
    manifest = read(tmp_path / "pilot/manifest.json")
    manifest["artifacts"]["report.json"] = file_sha(path)
    (tmp_path / "pilot/manifest.json").write_text(encoded(manifest), "utf-8")
    with pytest.raises(ValueError, match="Pilot reale"):
        freeze(tmp_path / "freeze.json", tmp_path / "invalid")


@pytest.mark.parametrize(("field", "value", "message"), [
    ("seed", 7, "Catena"),
    ("quotas", {"E0-v1": 2}, "Quote intere"),
    ("hours", 30, "Pilot reale"),
    ("model", " ", "modello"),
    ("semantic_overlap_review", "", "Piano incompleto"),
])
def test_freeze_rejects_inconsistent_plan(tmp_path, field, value, message):
    plan = freeze_fixture(tmp_path)
    plan[field] = value
    (tmp_path / "freeze.json").write_text(encoded(plan), "utf-8")
    with pytest.raises(ValueError, match=message):
        freeze(tmp_path / "freeze.json", tmp_path / "invalid")


def test_freeze_rejects_duplicate_assignment_and_corrupt_text(tmp_path):
    freeze_fixture(tmp_path)
    path = tmp_path / "assignments.jsonl"
    text = path.read_text("utf-8")
    path.write_text(text + text.splitlines()[0] + "\n", "utf-8")
    with pytest.raises(ValueError, match="duplicata"):
        freeze(tmp_path / "freeze.json", tmp_path / "invalid")
    path.write_text(text, "utf-8")
    packet = tmp_path / "packet/packet.json"
    packet.write_text(packet.read_text("utf-8") + " ", "utf-8")
    with pytest.raises(ValueError, match="Checksum"):
        freeze(tmp_path / "freeze.json", tmp_path / "invalid")
