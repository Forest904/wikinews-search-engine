"""Regression checks for benchmark conclusions that affect capacity and quality."""

from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts" / "performance"


@pytest.fixture
def campaign_module(monkeypatch):
    monkeypatch.syspath_prepend(str(SCRIPTS))
    import campaign

    return campaign


def test_confirms_both_edges(campaign_module, tmp_path, monkeypatch):
    runs = []

    def measure(args, label, rate, duration, mode):
        runs.append((rate, duration))
        return rate <= 5

    monkeypatch.setattr(campaign_module, "measure", measure)
    args = SimpleNamespace(output=tmp_path, mode="capacity", rate=1, max_rate=16)
    assert campaign_module.campaign(args)
    assert runs == [
        (1, "5m"),
        (2, "5m"),
        (4, "5m"),
        (8, "5m"),
        (6, "5m"),
        (5, "5m"),
        (5, "15m"),
        (6, "15m"),
    ]


def test_ceiling_does_not_claim_saturation(campaign_module, tmp_path, monkeypatch):
    import json

    monkeypatch.setattr(campaign_module, "measure", lambda *args: True)
    assert campaign_module.campaign(
        SimpleNamespace(output=tmp_path, mode="capacity", rate=1, max_rate=3)
    )
    assert json.loads((tmp_path / "capacity.json").read_text()) == {
        "tested_ceiling": 3,
        "confirmed": True,
        "saturation_observed": False,
    }


def test_percentile_requires_tail_samples(campaign_module):
    from engine import distribution

    assert distribution([]) == {"n": 0}
    assert distribution(range(100))["p95"] == 94
    assert distribution(range(999))["p99"] is None
    assert distribution(range(1000))["p99"] == 989
