import json

import pytest
from fastapi.testclient import TestClient

from wikinews_ir.api.main import create_app
from wikinews_ir.models import SearchRequest
from wikinews_ir.retrieval.highlight import segments
from wikinews_ir.retrieval.profiles import digest, profile_config
from wikinews_ir.retrieval.query_builder import build_query, parse_phrases


@pytest.mark.parametrize("query", ['""', '"  "', '"energia', 'energia”', '“energia"', '"a “b”"'])
def test_malformed_quotes(query):
    with pytest.raises(ValueError):
        SearchRequest(query=query, profile="E4")
    with TestClient(create_app()) as client:
        response = client.get("/api/search", params={"q": query, "profile": "E4"})
        assert response.status_code == 422
        assert "virgolette" in response.json()["detail"].lower()
    assert build_query(query, "E2")  # Quotes are ordinary analyzer input elsewhere.


def test_phrase_parser_and_independent_clauses():
    assert parse_phrases('“energia solare” Italia "pannelli nuovi"') == (
        "Italia", ["energia solare", "pannelli nuovi"])
    assert parse_phrases("l'energia") == ("l'energia", [])
    result = build_query('"energia solare" Italia Francia', "E4")["bool"]
    assert len(result["must"]) == 2
    assert result["must"][1]["multi_match"]["operator"] == "or"
    assert result["must"][0]["multi_match"]["slop"] == 0
    assert "fuzziness" not in json.dumps(result)
    assert build_query("energia solare", "E4")["bool"]["must"] == [build_query("energia solare", "E2")]
    fuzzy = build_query("energia", "E3")["bool"]
    assert fuzzy["minimum_should_match"] == 1
    assert fuzzy["should"][0] == build_query("energia", "E2")
    assert fuzzy["should"][1]["multi_match"]["boost"] == 0.2
    assert "phrase" not in json.dumps(fuzzy)


def test_highlight_decodes_text_without_interpreting_source_markup():
    result = segments(['&lt;mark&gt;&lt;script&gt;alert(1)&lt;/script&gt;&lt;/mark&gt; '
                       '<mark>energia</mark> &amp; sole'])
    assert ''.join(s['text'] for s in result) == '<mark><script>alert(1)</script></mark> energia & sole'
    assert [s['text'] for s in result if s['highlighted']] == ['energia']
    assert segments([]) == []


def test_profile_hashes_and_packaged_numeric_validation(tmp_path, monkeypatch):
    from wikinews_ir.retrieval import profiles
    configs = {p: profile_config(p) for p in profiles.SUPPORTED_PROFILES}
    assert len({digest(c) for c in configs.values()}) == 5
    import yaml
    folder = tmp_path / "retrieval"
    folder.mkdir()
    monkeypatch.setattr(profiles, "CONFIGS", tmp_path)
    c = configs["E2"]
    for bad in (True, 0, -1, float("nan"), "3"):
        c["title_boost"] = bad
        (folder / "E2.yaml").write_text(yaml.safe_dump(c))
        with pytest.raises(ValueError):
            profile_config("E2")
    c.update(title_boost=4.0, version="2")
    (folder / "E2.yaml").write_text(yaml.safe_dump(c))
    assert profile_config("E2")["title_boost"] == 4


def test_question_marks_are_ordinary_text():
    assert parse_phrases("energia?") == ("energia?", [])
