import pytest
from pydantic import ValidationError

from wikinews_ir.models import SearchRequest


@pytest.mark.parametrize("kwargs", [
    {"query": " "}, {"query": "x" * 251}, {"query": "x", "limit": 0},
    {"query": "x", "limit": 101}, {"query": "x", "profile": "fuzzy"},
])
def test_invalid_requests(kwargs):
    with pytest.raises(ValidationError):
        SearchRequest(**kwargs)


def test_normalized_request():
    assert SearchRequest(query="  calcio  ").query == "calcio"
    assert SearchRequest(query="x" * 250, limit=100).limit == 100
