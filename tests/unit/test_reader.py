import json
import sqlite3

from wikinews_ir.api.routes import templates
from wikinews_ir.reader import extract, read_page
from wikinews_ir.reader_build import credit


def test_reader_preserves_editorial_structure_and_resolves_related():
    markup = """<section><p>Prima <em>parola</em>.</p>
    <ul><li>Voce<ol><li>Dettaglio</li></ol></li></ul>
    <table><caption>Classifica</caption><tr><th colspan="2">Squadra</th></tr></table>
    <figure><img resource="./File:Icon.svg" src="//upload.wikimedia.org/icon.svg"></figure>
    <figure><img resource="./File:Foto.jpg" src="//upload.wikimedia.org/f.jpg"><figcaption>Piazza</figcaption></figure>
    <h2>Articoli correlati</h2><ul><li><a href="./Alias">Leggi</a></li></ul>
    <h2>Fonti</h2><ul><li>Giornale cartaceo</li></ul>
    <h2>Conclusione</h2><p onclick="alert(1)">Fine<script>bad()</script>
    <a href="javascript:bad()">testo</a></p></section>"""
    page = extract(markup, "https://it.wikinews.org/wiki/Test", {"Alias": "12"})
    assert page["file"] == "Foto.jpg"
    assert page["related"] == [{"href": "/articles/12", "label": "Leggi"}]
    assert page["sources"] == [{"href": "", "label": "Giornale cartaceo"}]
    render = templates.env.get_template("reader_blocks.html").module.render
    result = str(render(page["blocks"], None))
    assert '<th colspan="2">Squadra</th>' in result
    assert all(fragment in result for fragment in ["<ol>", "<ul>", "Fine", "<em>parola</em>"])
    assert all(fragment not in result for fragment in ["<figure", "onclick", "bad()", "Articoli correlati"])
    info = dict(thumburl="https://upload.wikimedia.org/photo.jpg", thumbwidth=800, thumbheight=600,
                descriptionurl="https://commons.wikimedia.org/wiki/File:Foto.jpg",
                extmetadata={k: {"value": v} for k, v in {
                    "Artist": "A. Rossi", "LicenseShortName": "CC BY 4.0",
                    "LicenseUrl": "https://creativecommons.org/licenses/by/4.0/",
                }.items()})
    image = credit(info)
    result = str(render(page["blocks"], {"Foto.jpg": image}))
    assert result.count("<figure") == 1 and "Piazza" in result and "A. Rossi" in result
    del info["extmetadata"]["Artist"]
    assert credit(info) is None


def test_repeated_figure_keeps_position_width_and_caption():
    def figure(align, width, caption):
        return f'<figure typeof="mw:File/Thumb" class="{align}"><img resource="./File:A.jpg" ' \
               f'src="//upload.wikimedia.org/A.jpg" width="{width}" height="80">' \
               f'<figcaption>{caption}</figcaption></figure>'

    markup = figure("", 120, "Prima") + "<p>Testo</p>" + figure("mw-halign-left", 180, "Seconda")
    page = extract(markup, "https://it.wikinews.org/wiki/Test", {})
    first, paragraph, second = page["blocks"]
    assert page["files"] == ["A.jpg"]
    assert paragraph["children"] == ["Testo"]
    assert (first["kind"], first["align"], first["width"], first["caption"]) == ("thumb", "right", 120, "Prima")
    assert (second["kind"], second["align"], second["width"], second["caption"]) == ("thumb", "left", 180, "Seconda")


def test_reader_fallback_for_other_snapshot_or_revision(tmp_path, monkeypatch):
    path = tmp_path / "catalog.sqlite3"
    monkeypatch.setenv("READER_CATALOG", str(path))
    assert read_page("1", "2", "sha") is None
    with sqlite3.connect(path) as db:
        db.executescript("CREATE TABLE manifest(checksum); INSERT INTO manifest VALUES ('sha');"
                         "CREATE TABLE pages(id,revision,file,payload); CREATE TABLE media(name,data);")
        db.execute("INSERT INTO pages VALUES ('1','2',NULL,?)", (json.dumps({"blocks": ["test"]}),))
    assert read_page("1", "2", "sha")["blocks"] == ["test"]
    assert read_page("1", "3", "sha") is None
    assert read_page("1", "2", "other") is None


def test_range_filter_keeps_relevance_query_and_rejects_reversed_years():
    from unittest.mock import Mock

    import pytest
    from pydantic import ValidationError

    from wikinews_ir.models import SearchRequest
    from wikinews_ir.retrieval.engine import RetrievalEngine

    backend = RetrievalEngine()
    backend.client.close()
    backend.client = Mock()
    backend.metadata = Mock(return_value={})
    backend.client.search.return_value = {"hits": {"total": {"value": 0}, "hits": []}}
    for bounds, expected in [
        ({"year_from": 2005}, {"gte": "2005-01-01"}),
        ({"year_to": 2006}, {"lte": "2006-12-31"}),
        ({"year_from": 2005, "year_to": 2005}, {"gte": "2005-01-01", "lte": "2005-12-31"}),
    ]:
        backend.search(SearchRequest(query="Roma", **bounds))
        query = backend.client.search.call_args.kwargs["query"]["bool"]
        assert query["must"] and query["filter"] == [{"range": {"publication_date": expected}}]
    with pytest.raises(ValidationError):
        SearchRequest(query="Roma", year_from=2010, year_to=2009)
