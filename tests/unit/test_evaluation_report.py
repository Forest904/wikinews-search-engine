import csv
import math
import subprocess
import sys
from pathlib import Path
from xml.etree import ElementTree

import pytest

from wikinews_ir.evaluation.artifacts import verify_bundle
from wikinews_ir.evaluation.report import agreement, evaluate


@pytest.fixture
def inputs(tmp_path):
    root = tmp_path/"fixture"
    script = Path(__file__).resolve().parents[2]/"scripts"/"m6a_fixture.py"
    subprocess.run([sys.executable, str(script), str(root)], check=True)
    return root


def table(root, name):
    with (root/name).open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream, delimiter="\t"))


def test_cli_report(inputs):
    root = inputs
    out = root/"report"
    subprocess.run([sys.executable, "-m", "wikinews_ir.cli", "benchmark", "evaluate", "--topics",
                    str(root/"topics.jsonl"), "--split", "development", "--runs", str(root/"profile"),
                    str(root/"external"), "--gold", str(root/"gold"), "--silver", str(root/"silver"),
                    "--output", str(out), "--fixture"], check=True)
    meta = verify_bundle(out, "evaluation-report")["metadata"]
    assert meta["fixture"] and meta["denominators"]["gold"] == {
        "MRR@10": 1, "nDCG@10": 2, "P@5": 2}
    rows = {(r["query_id"], r["run"], r["source"]): r for r in table(out, "metrics.tsv")}
    event = rows["E", "E0-v1", "gold"]
    assert float(event["nDCG@10"]) == pytest.approx(1/math.log2(3))
    assert float(event["P@5"]) == 0.2 and float(event["MRR@10"]) == 0.5
    assert float(rows["E", "wikimedia", "gold"]["MRR@10"]) == 1
    assert rows["U", "E0-v1", "gold"]["P@5"] == "N/D"
    assert rows["T", "E0-v1", "gold"]["MRR@10"] == "N/D"
    assert float(rows["T", "E0-v1", "gold"]["P@5"]) == 0
    assert all(q != "X" for q, _, _ in rows)
    coverage = table(out, "coverage.tsv")
    first = coverage[0]
    assert [first[k] for k in ("returned", "judged", "unjudged", "abstained", "coverage")] == [
        "2", "1", "1", "1", "0.5"]
    assert all(r["coverage"] == "N/D" for r in coverage if r["query_id"] == "T")
    ElementTree.parse(out/"coverage.svg")
    assert meta["agreement"] == pytest.approx(dict(shared=2, macro_F1=1/3, linear_kappa=0.5))
    assert table(out, "disagreements.tsv") == [dict(query_id="E", document_id="b", gold="2",
                                                    silver="1")]
    assert [list(r.values())[1:] for r in table(out, "confusion.tsv")] == [
        ["1", "0", "0"], ["0", "0", "0"], ["0", "1", "0"]]


def test_invalid_inputs(inputs):
    root = inputs
    args = root/"topics.jsonl", "test", [root/"profile"], root/"report"
    with pytest.raises(ValueError, match="split"):
        evaluate(*args, gold=root/"gold")
    with pytest.raises(ValueError, match="fonte"):
        evaluate(*args)
    (root/"profile"/"E0.trec").write_text("altered")
    with pytest.raises(ValueError, match="Checksum"):
        evaluate(*args, silver=root/"silver")
    assert not (root/"report").exists()


def test_undefined_agreement():
    assert agreement({}, {})[2] == dict(shared=0, macro_F1=None, linear_kappa=None)
    labels = {("q", "a"): 0}
    assert agreement(labels, labels)[2]["linear_kappa"] is None
