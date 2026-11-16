import hashlib
import io
import json
import tarfile

import httpx
import pytest

from wikinews_ir.ingestion import acquisition as acq


@pytest.fixture
def snapshot(monkeypatch):
    record = {
        "identifier": 1,
        "version": {"identifier": 2},
        "name": "Notizia",
        "url": "https://it.wikinews.org/wiki/Notizia",
        "namespace": {"identifier": 0},
        "in_language": {"identifier": "it"},
        "article_body": {"html": "<p>Testo.</p>"},
        "categories": [{"name": "Categoria:Pubblicati"}],
    }
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w:gz") as tar:
        data = (json.dumps(record) + "\n").encode()
        member = tarfile.TarInfo("input.ndjson")
        member.size = len(data)
        tar.addfile(member, io.BytesIO(data))
    content = stream.getvalue()
    monkeypatch.setattr(acq, "SIZE", len(content))
    monkeypatch.setattr(acq, "SHA256", hashlib.sha256(content).hexdigest())
    monkeypatch.setattr(acq.time, "sleep", lambda _: None)
    return content


def mock_http(monkeypatch, handler):
    client = httpx.Client
    monkeypatch.setattr(
        acq.httpx,
        "Client",
        lambda **kwargs: client(transport=httpx.MockTransport(handler), **kwargs),
    )


def test_prepare_download_and_offline_reuse(tmp_path, monkeypatch, snapshot):
    requests = []

    def handler(request):
        requests.append(request)
        assert request.headers["User-Agent"] == acq.USER_AGENT
        if request.url.path.endswith("tar.gz"):
            return httpx.Response(302, headers={"location": "https://example.org/file"})
        return httpx.Response(200, stream=httpx.ByteStream(snapshot))

    mock_http(monkeypatch, handler)
    raw, output = tmp_path / "raw", tmp_path / "out"
    result = acq.prepare(raw, output)
    assert result["counts"]["articles_produced"] == 1
    assert len(requests) == 2
    monkeypatch.setattr(acq.httpx, "Client", lambda **kw: pytest.fail("Network on reuse"))
    monkeypatch.setattr(acq.corpus, "run_corpus", lambda *a, **kw: pytest.fail("Rebuild on reuse"))
    assert acq.prepare(raw, output) == result


@pytest.mark.parametrize(
    "failure",
    [403, 404, 429, 500, "timeout", "interrupted", "checksum", "short", "large", "insecure"],
)
def test_download_errors_leave_no_archive(tmp_path, monkeypatch, snapshot, failure):
    calls = []

    class Broken(httpx.SyncByteStream):
        def __iter__(self):
            yield snapshot[:10]
            raise httpx.ReadError("connection lost")

    def handler(request):
        calls.append(request)
        if isinstance(failure, int):
            return httpx.Response(failure)
        if failure == "timeout":
            raise httpx.ReadTimeout("timeout", request=request)
        if failure == "interrupted":
            return httpx.Response(200, stream=Broken())
        if failure == "insecure":
            return httpx.Response(302, headers={"location": "http://example.org/file"})
        data = {"checksum": b"x" * len(snapshot), "short": snapshot[:-1], "large": snapshot + b"x"}[
            failure
        ]
        return httpx.Response(200, stream=httpx.ByteStream(data))

    mock_http(monkeypatch, handler)
    with pytest.raises(ValueError):
        acq.acquire(tmp_path)
    assert not list(tmp_path.iterdir())
    assert len(calls) == (3 if failure in (429, 500, "timeout", "interrupted") else 1)


def test_retry_then_success(tmp_path, monkeypatch, snapshot):
    calls = []

    def handler(request):
        calls.append(request)
        return (
            httpx.Response(503)
            if len(calls) == 1
            else httpx.Response(200, stream=httpx.ByteStream(snapshot))
        )

    mock_http(monkeypatch, handler)
    assert acq.acquire(tmp_path).read_bytes() == snapshot
    assert len(calls) == 2


def test_existing_bad_archive_preserved(tmp_path, monkeypatch, snapshot):
    path = tmp_path / acq.FILENAME
    path.write_bytes(b"bad")
    monkeypatch.setattr(acq.httpx, "Client", lambda **kw: pytest.fail("Network"))
    with pytest.raises(ValueError, match="Archivio locale diverso"):
        acq.acquire(tmp_path)
    assert path.read_bytes() == b"bad"


@pytest.mark.parametrize(
    "change", ["artifact", "missing", "pipeline", "dependencies", "invalid", "malformed"]
)
def test_incompatible_corpus_preserved(tmp_path, monkeypatch, snapshot, change):
    raw, output = tmp_path / "raw", tmp_path / "out"
    raw.mkdir()
    (raw / acq.FILENAME).write_bytes(snapshot)
    acq.prepare(raw, output)
    path = output / "manifest.json"
    manifest = json.loads(path.read_text())
    if change == "artifact":
        (output / "articles.ndjson").write_text("changed")
    elif change == "missing":
        (output / "audit.json").unlink()
    elif change == "pipeline":
        manifest["pipeline_source_sha256"] = "old"
    elif change == "dependencies":
        manifest["execution"]["dependencies"]["lxml"] = "old"
    elif change == "invalid":
        manifest["valid"] = False
    path.write_text("[]" if change == "malformed" else json.dumps(manifest))
    before = {p.name: p.read_bytes() for p in output.iterdir()}
    with pytest.raises(ValueError, match="--output"):
        acq.prepare(raw, output)
    assert before == {p.name: p.read_bytes() for p in output.iterdir()}


def test_cli_prepare(tmp_path, monkeypatch, snapshot, capsys):
    from wikinews_ir.cli import main

    mock_http(monkeypatch, lambda request: httpx.Response(200, stream=httpx.ByteStream(snapshot)))
    monkeypatch.setattr(
        "sys.argv",
        [
            "wikinews-ir",
            "corpus",
            "prepare",
            "--raw-dir",
            str(tmp_path / "raw"),
            "--output",
            str(tmp_path / "out"),
        ],
    )
    main()
    assert "Corpus pronto" in capsys.readouterr().out


def test_user_interrupt_cleans_temporary(tmp_path, monkeypatch, snapshot):
    class Interrupted(httpx.SyncByteStream):
        def __iter__(self):
            yield snapshot[:10]
            raise KeyboardInterrupt

    mock_http(monkeypatch, lambda request: httpx.Response(200, stream=Interrupted()))
    with pytest.raises(KeyboardInterrupt):
        acq.acquire(tmp_path)
    assert not list(tmp_path.iterdir())
