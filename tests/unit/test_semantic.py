import json
import math

import httpx
import pytest
from tokenizers import Tokenizer, models, pre_tokenizers

from wikinews_ir.ingestion.corpus import clean_html
from wikinews_ir.models import SearchRequest
from wikinews_ir.semantic import DIM, embed, opening, prepare


def test_semantic_html_preserves_reporting_and_original_reader():
    html = """<p>Il <a href="https://example.org">sindaco</a> ha detto:
    «Non è chiusa».</p><figure><figcaption>Foto di ieri</figcaption></figure>
    <h2>Articoli correlati</h2><p>Altro articolo</p><h2>Sviluppi</h2><p>La replica.</p>"""
    text = clean_html(html, semantic=True)[0]
    assert "sindaco" in text and "«Non è chiusa»" in text and "La replica" in text
    assert "Altro articolo" not in text and "Foto di ieri" not in text
    assert "Foto di ieri" in clean_html(html)[0]


def test_opening_and_encoder_budget():
    tok = Tokenizer(models.WordLevel({"test": 0, "[UNK]": 1}, unk_token="[UNK]"))
    tok.pre_tokenizer = pre_tokenizers.Whitespace()
    article = {
        "document_id": "1",
        "revision_id": "2",
        "url": "",
        "publication_date": "2005-03-31",
        "publication_date_status": "validated",
        "title": "Titolo",
    }
    body = "31 marzo 2005\nVedi https://example.org\n" + "test " * 500
    row = prepare(article, body, tok, "natural")
    assert len(tok.encode(row["input"]).ids) == row["tokens"] == 256
    assert row["input"].startswith("title: Titolo\ncontent: Vedi\n")
    assert row["year"] == 2005
    assert opening("31 marzo 2005\nNotizia", "2005-03-30").startswith("31 marzo")
    assert opening("Roma, giovedì 31 marzo 2005\nNotizia", "2005-03-31") == "Roma\nNotizia"
    assert prepare(article, "", tok, "natural")["title"] == "Titolo"
    assert prepare({**article, "title": ""}, "", tok, "natural") is None
    assert prepare({**article, "title": "test " * 400}, "", tok, "natural")["tokens"] == 256


def test_parsoid_navigation_spread_over_siblings():
    html = """<section><div about="#mwt1"><img src="banner.png"></div>
      <div about="#mwt1"><p>Tutti gli articoli dello Speciale:</p><ul><li>Altro</li></ul></div>
      <table about="#mwt2" data-mw='{"parts":[{"template":{"target":{"wt":"InfoboxSisma"}}}]}'>
      <tr><td>Riquadro</td></tr></table><p>Il racconto del sisma.</p></section>"""
    assert clean_html(html, semantic=True)[0] == "Il racconto del sisma."


@pytest.mark.parametrize("vector", [[0] * DIM, [1], [1] * DIM])
def test_ollama_vector_validation(vector):
    with httpx.Client(
        base_url="http://ollama",
        transport=httpx.MockTransport(
            lambda _: httpx.Response(200, json={"embeddings": [vector], "prompt_eval_count": 2})
        ),
    ) as http:
        if len(vector) == DIM and vector[0]:
            assert math.hypot(*embed(http, ["query: test"], 2)[0]) == pytest.approx(1)
        else:
            with pytest.raises(ValueError):
                embed(http, ["query: test"])


def test_semantic_page_uses_archive_search_contract():
    assert SearchRequest(query=" notizia ", profile="semantic", year_from=2000).query == "notizia"
    with pytest.raises(ValueError):
        SearchRequest(query="notizia", profile="semantic", year_from=2022, year_to=2000)


def test_filtered_ties_are_stable_across_page_boundary(monkeypatch):
    from wikinews_ir import semantic
    from wikinews_ir.retrieval.profiles import digest

    encoder = {"digest": "fixture"}
    name = f"news-{digest(encoder)[:24]}-natural-fixture"
    ids = ["3", "2", "1", "0"]

    def respond(request):
        if request.url.path == "/aliases":
            result = {"aliases": [{"alias_name": semantic.ALIAS, "collection_name": name}]}
        else:
            body = json.loads(request.content)
            assert body["filter"] == {"must": [{"key": "year", "range": {"gte": 2000}}]}
            if request.url.path.endswith("/count"):
                result = {"count": 4}
            else:
                result = {
                    "points": [
                        {"score": 0.5, "payload": {"document_id": doc, "title": doc, "url": ""}}
                        for doc in ids[: body["limit"]]
                    ]
                }
        return httpx.Response(200, json={"result": result})

    monkeypatch.setattr(
        semantic,
        "client",
        lambda _: httpx.Client(base_url="http://fixture", transport=httpx.MockTransport(respond)),
    )
    monkeypatch.setattr(semantic, "identity", lambda _: encoder)
    monkeypatch.setattr(semantic, "embed", lambda *_: [[1.0]])
    for page in (1, 2, 5):
        response = semantic.search(
            SearchRequest(
                query="notizia", profile="semantic", year_from=2000, page=page, page_size=1
            )
        )
        assert response.total == 4
        assert [h.document_id for h in response.hits] == ([str(page - 1)] if page < 5 else [])


def test_document_batch_uses_runtime_count_and_shortens_only_overflow(monkeypatch):
    from wikinews_ir import semantic

    rows = [{"input": "a" * 236, "tokens": 236}, {"input": "b" * 256, "tokens": 256}]

    def measured(_, texts):
        return [[1.0] for text in texts], sum(len(text) + 2 for text in texts)

    class Characters:
        def encode(self, text):
            from types import SimpleNamespace

            return SimpleNamespace(ids=list(text), offsets=[(i, i + 1) for i in range(len(text))])

    monkeypatch.setattr(semantic, "measured_embeddings", measured)
    assert semantic.embed_documents(None, rows, Characters()) == [[1.0], [1.0]]
    assert [(len(r["input"]), r["tokens"]) for r in rows] == [(236, 238), (254, 256)]
