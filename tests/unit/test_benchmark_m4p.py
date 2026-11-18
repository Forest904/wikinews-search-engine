import importlib.util
from pathlib import Path

import httpx
import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/benchmark_m4p.py"
spec = importlib.util.spec_from_file_location("benchmark_m4p", SCRIPT)
bench = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bench)


def test_session_order_and_empty_results():
    queries = [{"query_id": q, "query": q} for q in ("uno", "due")]
    profiles = {p: {"index": p} for p in ("E0", "E1")}
    calls = []

    def respond(request):
        params = request.url.params
        profile, query = params["profile"], params["q"]
        assert request.url.path == "/api/search"
        assert (params["page"], params["page_size"]) == ("1", "10")
        calls.append((profile, query))
        return httpx.Response(200, json=dict(query=query, profile=profile, index=profile,
                              metadata=profiles[profile], hits=[], total=0, elapsed_ms=0))

    with httpx.Client(base_url="http://test", transport=httpx.MockTransport(respond)) as client:
        samples = list(bench.session_samples(client, 1, queries, profiles))
    assert calls == [(p, q["query"]) for p in profiles for _ in range(6) for q in queries]
    assert sum(s["phase"] == "warmup" for s in samples) == 4
    assert all(s["error"] is None and s["es_ms"] == 0 for s in samples)


def test_summary_percentiles_and_failures():
    rows = [dict(client_ms=i, es_ms=2*i, phase="measure", error=None) for i in range(1, 21)]
    rows.extend([dict(phase="warmup", error="timeout"), dict(phase="measure", error="HTTP 503")])
    assert bench.summarize(rows) == dict(
        requests=21, errors=1, warmup_errors=1, client_ms=dict(median=10.5, p95=19),
        es_ms=dict(median=21, p95=38))
    assert bench.summarize(rows[-1:])["client_ms"]["p95"] is None


@pytest.mark.parametrize("failure", ["timeout", "http", "json", "fixture"])
def test_invalid_search(failure):
    def respond(request):
        if failure == "timeout":
            raise httpx.ReadTimeout("timeout")
        if failure == "fixture":
            return httpx.Response(200, json=dict(query="uno", profile="E0", index="fixture",
                                                 metadata={}, hits=[], elapsed_ms=1))
        return httpx.Response(503 if failure == "http" else 200, content=b"<html>")

    with httpx.Client(base_url="http://test", transport=httpx.MockTransport(respond)) as client:
        sample = bench.request_sample(client, {"query": "uno"}, "E0", {"index": "real"})
    assert sample["error"] and sample["es_ms"] is None and sample["client_ms"] >= 0


def test_existing_output(tmp_path):
    with pytest.raises(FileExistsError):
        bench.benchmark(tmp_path, "http://test")
