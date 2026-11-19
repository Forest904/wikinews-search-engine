import csv

import pytest
from filelock import FileLock

from wikinews_ir.evaluation import m6b
from wikinews_ir.evaluation.artifacts import write_bundle
from wikinews_ir.evaluation.m6b_analysis import PROFILES, analyze, select_candidate


def test_paired_views_and_variants():
    topics = {q: dict(query=q, type="multi-constraint") for q in ["A", "B", "U"]}
    runs = {r: {"A": ["u", "a", "b"], "B": [], "U": []} for r in PROFILES}
    runs[PROFILES[3]] = dict(runs[PROFILES[2]], A=["b", "u", "a"])
    gold = {("A", "a"): 2, ("A", "b"): 0, ("B", "c"): 1}
    silver = {**gold, ("A", "a"): 0, ("A", "b"): 2, ("A", "u"): 2}
    variants = {r: {"A-1": ["a"], "A-2": [], "B-1": [], "U-1": []} for r in PROFILES[2:4]}
    files, summary = analyze(topics, runs, dict(gold=gold, silver=silver), variants)
    assert select_candidate(summary) == PROFILES[0]
    summary[PROFILES[1]] = {**summary[PROFILES[0]], "P@5": 1}
    assert select_candidate(summary) == PROFILES[1]

    def table(name):
        return list(csv.DictReader(files[name].splitlines(), delimiter="\t"))

    assert any(
        row["change"] == "inversione" and row["first"] == "gold/shared"
        for row in table("ordering.tsv")
    )
    rows = [r for r in table("typos.tsv") if r["metric"] == "nDCG@10" and r["run"] == PROFILES[2]]
    assert [r["perturbed"] for r in rows] == ["0.5", "0.0", "N/D"]
    assert any(r["view"] == "condensed" and r["topics"] == "2" for r in table("views.tsv"))


def test_final_gate_recovery_and_replay(tmp_path, monkeypatch):
    root = tmp_path / "report"
    monkeypatch.setattr(m6b, "ROOT", root)
    monkeypatch.setattr(m6b, "VARIANTS", root / "variants")
    monkeypatch.setattr(m6b, "inputs", lambda: ([], {}))
    monkeypatch.setattr(m6b, "identities", lambda: {})
    index = tmp_path / "index"
    index.write_text('{"sha256":{}}')
    monkeypatch.setattr(m6b, "INDEX", index)
    monkeypatch.setattr(m6b, "TOPICS", index)
    monkeypatch.setattr(m6b, "RUNS", [])
    write_bundle(m6b.VARIANTS, "variants", {})
    monkeypatch.setattr(m6b, "variant_runs", lambda *args: {})
    calls = []

    def simulate(split, topics, variants, dest):
        calls.append(split)
        if calls == ["development", "test"]:
            raise OSError("interrupted")
        for name in ("silver", "canonical", "analysis"):
            write_bundle(
                dest / name,
                name,
                {},
                {
                    "code_and_inputs": {},
                    "variant_manifest": m6b.file_sha(m6b.VARIANTS / "manifest.json"),
                    "gold": {r: {"nDCG@10": 1, "P@5": 1} for r in PROFILES},
                },
            )

    monkeypatch.setattr(m6b, "run_split", simulate)
    m6b.experiment("development")
    with pytest.raises(ValueError, match="Congelamento"):
        m6b.experiment("final")
    assert calls == ["development"]
    m6b.experiment("freeze")
    with FileLock(str(root / "experiment.lock")), pytest.raises(ValueError, match="in corso"):
        m6b.experiment("final")
    with pytest.raises(OSError, match="interrupted"):
        m6b.experiment("final")
    m6b.experiment("final")
    assert m6b.experiment("final")["event"] == "complete"
    assert calls == ["development", "test", "test"]
    (root / "freeze/protocol.json").write_text("{}")
    with pytest.raises(ValueError, match="Checksum"):
        m6b.experiment("final")
