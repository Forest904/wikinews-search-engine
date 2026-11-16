import io
import json
import tarfile

import pytest

from wikinews_ir.ingestion.corpus import clean_html, run_corpus


def record(ident=1, revision=1, *, published=True, html="<p>Una notizia.</p>"):
    return {
        "identifier": ident,
        "version": {"identifier": revision},
        "name": "Titolo",
        "url": "https://it.wikinews.org/wiki/Titolo",
        "namespace": {"identifier": 0},
        "in_language": {"identifier": "it"},
        "article_body": {"html": html},
        "categories": [{"name": "Categoria:Pubblicati"}] if published else [],
        "license": [],
    }


def write_input(tmp_path, items):
    source = tmp_path / "input.ndjson"
    source.write_text("".join(json.dumps(r) + "\n" for r in items), encoding="utf-8")
    return source


def read_articles(output):
    return [
        json.loads(line)
        for line in (output / "articles.ndjson").read_text(encoding="utf-8").splitlines()
    ]


def test_latest_revision_before_selection_and_accounting(tmp_path):
    source = write_input(
        tmp_path,
        [
            record(2, 5),
            record(1, 3, published=False),
            record(1, 1),
            record(2, 2, published=False),
            record(2, 5),
        ],
    )
    result = run_corpus(source, tmp_path / "out")
    assert [a["document_id"] for a in read_articles(tmp_path / "out")] == ["2"]
    counts = result["counts"]
    assert counts["records_read"] == 5
    assert counts["superseded_revisions"] == 2
    assert counts["identical_duplicate"] == 1
    assert counts["pages_excluded"] == 1
    assert counts["articles_produced"] == 1


def test_reproducible_archive_and_plain(tmp_path):
    source = write_input(tmp_path, [record(2), record(1)])
    archive = tmp_path / "input.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        data = source.read_bytes()
        member = tarfile.TarInfo("../../input.ndjson")
        member.size = len(data)
        tar.addfile(member, io.BytesIO(data))
    run_corpus(source, tmp_path / "a")
    run_corpus(source, tmp_path / "b")
    run_corpus(archive, tmp_path / "c")
    assert (tmp_path / "a/articles.ndjson").read_bytes() == (
        tmp_path / "b/articles.ndjson"
    ).read_bytes()
    plain, packed = read_articles(tmp_path / "a"), read_articles(tmp_path / "c")
    for articles in (plain, packed):
        for article in articles:
            article.pop("provenance")
    assert plain == packed
    assert not (tmp_path.parent / "input.ndjson").exists()


@pytest.mark.parametrize("fault", ["json", "schema", "conflict", "truncated"])
def test_invalid_build_is_atomic_audit_reports(tmp_path, fault):
    source = write_input(tmp_path, [record()])
    if fault == "json":
        source.write_text(source.read_text() + "{broken\n")
    elif fault == "schema":
        source.write_text(source.read_text() + '{"identifier":true}\n')
    elif fault == "conflict":
        source = write_input(tmp_path, [record(), record(html="<p>Different</p>")])
    else:
        source = tmp_path / "broken.tar.gz"
        source.write_bytes(b"broken")
    with pytest.raises(ValueError):
        run_corpus(source, tmp_path / "out")
    assert not (tmp_path / "out").exists()
    result = run_corpus(source, tmp_path / "audit", audit_only=True)
    assert not result["valid"]
    assert not (tmp_path / "audit/articles.ndjson").exists()
    assert (tmp_path / "audit/decisions.ndjson").read_text()


def test_cleaner_preserves_information_and_separates_sources():
    html = """<html><head><title>Duplicate title</title></head><body>
    <p>Una <b>notizia</b> italiana.</p><table><tr><th>Squadra</th><td>3</td></tr></table>
    <figure><figcaption>Una didascalia</figcaption></figure>
    <div class="boilerplate">Condividi</div><h2>Fonti</h2>
    <ul><li><cite>Fonte <a href="https://example.org">titolo</a></cite></li></ul>
    <div class="metadata">Avviso</div><h2>Approfondimento</h2><p>Testo da mantenere</p>
    <h2>Articoli correlati</h2><ul><li>Altro titolo</li></ul></body></html>"""
    body, sources, *_ = clean_html(html)
    for text in ("Una notizia italiana.", "Squadra", "3", "Una didascalia", "Testo da mantenere"):
        assert text in body
    for text in ("Duplicate title", "Condividi", "Avviso", "Fonte", "Altro titolo"):
        assert text not in body
    assert sources == [{"text": "Fonte titolo", "urls": ["https://example.org"]}]


def date_html(value, template="Data"):
    key = "1" if template == "Data" else "data"
    data = {
        "parts": [
            {
                "template": {
                    "target": {"href": f"./Template:{template}"},
                    "params": {key: {"wt": value}},
                }
            }
        ]
    }
    return f"<b data-mw='{json.dumps(data)}'>data</b>"


def test_original_news_notice_and_calendar_navigation():
    data = {"parts": [{"template": {"target": {"href": "./Template:Notizia_originale"}}}]}
    html = (
        '<p>Risultato 3-1<sup class="reference">[1]</sup>.</p>'
        f"<table data-mw='{json.dumps(data)}'><tr><td>Notizia originale</td></tr></table>"
        "<p>Per vedere il calendario completo vai alla pagina Speciale Serie B.</p>"
        "<table><tr><td>Squadra</td><td>3</td></tr></table>"
    )
    body, *_ = clean_html(html)
    assert "Risultato 3-1." in body
    assert "Squadra" in body
    assert "Notizia originale" not in body
    assert "calendario completo" not in body


@pytest.mark.parametrize(
    ("html", "expected"),
    [
        ("<p>20 marzo 2025</p>", "missing"),
        (date_html("20 marzo 2025"), "validated"),
        (date_html("20 marzo 2025", "Luogodata"), "validated"),
        (date_html("31 febbraio 2025"), "invalid"),
        (date_html("20 marzo 2025") + date_html("21 marzo 2025"), "ambiguous"),
        (date_html("20 marzo 2025") + date_html("ignota"), "invalid"),
    ],
)
def test_publication_dates(html, expected):
    _, _, value, status, _ = clean_html(html)
    assert status == expected
    assert (value is not None) == (status == "validated")


def test_redirect_aliases_are_not_redirect_pages_and_empty_body(tmp_path):
    alias = record(1)
    alias["redirects"] = [{"url": "https://it.wikinews.org/wiki/Alias"}]
    source = write_input(
        tmp_path,
        [
            alias,
            record(2, html='<link rel="mw:PageProp/redirect" href="./Other"/>'),
            record(3, html='<div class="metadata">Avviso</div>'),
        ],
    )
    run_corpus(source, tmp_path / "out")
    assert [a["document_id"] for a in read_articles(tmp_path / "out")] == ["1"]
    with pytest.raises(ValueError, match="absent or empty"):
        run_corpus(source, tmp_path / "out")


@pytest.mark.parametrize("archive", [False, True])
def test_empty_input_is_not_certified(tmp_path, archive):
    source = tmp_path / ("empty.tar.gz" if archive else "empty.ndjson")
    if archive:
        with tarfile.open(source, "w:gz"):
            pass
    else:
        source.write_bytes(b"")
    with pytest.raises(ValueError):
        run_corpus(source, tmp_path / "out")
    result = run_corpus(source, tmp_path / "audit", audit_only=True)
    assert not result["valid"]


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    [
        ("namespace", {"identifier": 1}, "namespace"),
        ("in_language", {"identifier": "en"}, "language"),
        ("url", "https://example.org/wiki/Test", "invalid_url"),
    ],
)
def test_eligibility_rejections(tmp_path, field, value, reason):
    item = record()
    item[field] = value
    run_corpus(write_input(tmp_path, [item]), tmp_path / "out")
    audit = json.loads((tmp_path / "out/audit.json").read_text())
    assert audit["excluded_by_reason"] == {reason: 1}


def test_cli_corpus_dispatch_and_error_status(tmp_path, monkeypatch, capsys):
    from wikinews_ir.cli import main

    source = write_input(tmp_path, [record()])
    args = [
        "wikinews-ir",
        "corpus",
        "build",
        "--input",
        str(source),
        "--output",
        str(tmp_path / "out"),
    ]
    monkeypatch.setattr("sys.argv", args)
    main()
    assert '"articles_produced": 1' in capsys.readouterr().out
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 1


def test_multiple_archive_members_deduplicate_globally(tmp_path):
    from wikinews_ir.ingestion.corpus import checksum

    source = tmp_path / "multiple.tar.gz"
    with tarfile.open(source, "w:gz") as tar:
        for name, item in (("a.ndjson", record(1, 5)), ("b.ndjson", record(1, 2))):
            data = (json.dumps(item) + "\n").encode()
            member = tarfile.TarInfo(name)
            member.size = len(data)
            tar.addfile(member, io.BytesIO(data))
        link = tarfile.TarInfo("link.ndjson")
        link.type = tarfile.SYMTYPE
        link.linkname = "a.ndjson"
        tar.addfile(link)
    output = tmp_path / "out"
    manifest = run_corpus(source, output)
    articles = read_articles(output)
    assert len(articles) == 1
    assert articles[0]["revision_id"] == "5"
    assert articles[0]["provenance"]["member"] == "a.ndjson"
    assert manifest["counts"]["records_read"] == 2
    for name, expected in manifest["artifacts"].items():
        assert checksum(output / name) == expected
