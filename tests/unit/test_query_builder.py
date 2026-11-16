import pytest

from wikinews_ir.retrieval.query_builder import build_query


def test_valid_bm25_query():
    assert build_query("  terremoto  ") == {
        "multi_match": {"query": "terremoto", "fields": ["title", "body"]}
    }


def test_unsupported_profile_is_rejected():
    with pytest.raises(ValueError, match="not implemented"):
        build_query("calcio", "fuzzy")


def test_blank_query_is_rejected():
    with pytest.raises(ValueError, match="vuota"):
        build_query(" ")
