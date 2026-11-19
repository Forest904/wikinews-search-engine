from unittest.mock import Mock

import pytest

from wikinews_ir.retrieval.terms import missing_terms, query_words


@pytest.mark.parametrize(("query", "title", "body", "expected"), [
    ("Roma Milano tram milano", "ROMA", "tramonto", ["Milano", "tram"]),
    ("l’acqua caffè del nord-est", "L'acqua", "x " * 240 + "caffe\u0300 del nord est", []),
    ("caffè in città", "", "caffe", ["caffè", "in", "città"]),
    ("", "Roma", "Milano", []),
    ("tram", "Roma", None, []),
])
def test_literal_article_words(query, title, body, expected):
    assert missing_terms(query_words(query), {"title": title, "body": body}) == expected


def test_semantic_terms_follow_document_ids(monkeypatch):
    from wikinews_ir.models import SearchHit, SearchRequest, SearchResponse
    from wikinews_ir.retrieval.engine import RetrievalEngine

    request = SearchRequest(query="Roma tram", profile="semantic")
    hits = [SearchHit(document_id=key, title="Cronaca", url="", rank=i, score=1)
            for i, key in enumerate(("a", "b", "c"), 1)]
    response = SearchResponse(query=request.query, profile="semantic", index="test",
                              hits=hits, elapsed_ms=1)
    monkeypatch.setattr("wikinews_ir.semantic.search", lambda request: response)
    engine = RetrievalEngine()
    engine.client.close()
    engine.client = Mock()
    engine.client.mget.return_value = {"docs": [
        {"_id": "b", "found": True, "_source": {"title": "Roma", "body": "cronaca"}},
        {"_id": "c", "found": False},
        {"_id": "a", "found": True, "_source": {"title": "Milano", "body": "cronaca"}},
    ]}
    assert [hit.missing_terms for hit in engine.search(request).hits] == [
        ["Roma", "tram"], ["tram"], [],
    ]
    engine.client.mget.assert_called_once()
