import sqlite3
from unittest.mock import Mock

import httpx
import pytest
from fastapi.testclient import TestClient

from wikinews_ir import reader_build
from wikinews_ir.adapters.live import LiveSearch
from wikinews_ir.adapters.mediawiki import MediaWiki
from wikinews_ir.api.main import create_app
from wikinews_ir.api.routes import engine


def test_live_cache_pagination_links_and_optional_images():
    calls = []

    def respond(request):
        params = request.url.params
        calls.append(params)
        if "sroffset" in params:
            body = {"query": {"search": []}}
        elif "list" in params:
            body = {
                "query": {
                    "search": [
                        {"pageid": i, "title": str(i), "snippet": "<b>x</b>"} for i in (7, 9)
                    ]
                },
                "continue": {"continue": "-||", "sroffset": 2},
            }
        elif params["prop"] == "pageimages":
            body = {"query": {"pages": [{"pageid": i, "pageimage": "Photo.jpg"} for i in (7, 9)]}}
        else:
            assert params["titles"] == "File:Photo.jpg"
            body = {
                "query": {
                    "pages": [
                        {
                            "title": "File:Photo.jpg",
                            "imageinfo": [
                                {
                                    "thumburl": "https://thumb.wikimedia.org/photo.jpg",
                                    "thumbwidth": 320,
                                    "thumbheight": 240,
                                    "descriptionurl": "https://commons.wikimedia.org/wiki/File:Photo.jpg",
                                    "extmetadata": {"LicenseShortName": {"value": "Public domain"}},
                                }
                            ],
                        }
                    ]
                }
            }
        return httpx.Response(200, json=body)

    app = create_app()
    backend = Mock()
    backend.archived_ids.return_value = {"7"}
    app.dependency_overrides[engine] = lambda: backend
    with (
        TestClient(app) as client,
        httpx.Client(transport=httpx.MockTransport(respond)) as upstream,
    ):
        app.state.wikinews = LiveSearch(MediaWiki(client=upstream))
        endpoint = "/api/search/live"
        page = client.get(endpoint, params={"q": "prova"}).json()
        one, two = page["hits"]
        assert one["snippet"] == "x" and one["local_url"] == "/articles/7"
        assert two["local_url"] is None and two["image"]["width"] == 320
        assert client.get(endpoint, params={"q": "prova"}).json() == page
        assert len(calls) == 3
        assert (
            client.get(endpoint, params={"q": "prova", "cursor": page["next_cursor"]}).json()[
                "hits"
            ]
            == []
        )
        assert client.get(endpoint, params={"q": "prova", "cursor": "bogus"}).status_code == 422


def test_resume_legacy_null_and_retry_after(monkeypatch):
    waits = []
    responses = iter(
        [
            httpx.Response(429, headers={"Retry-After": "4"}),
            httpx.Response(200, json={"query": {"pages": []}}),
        ]
    )
    with httpx.Client(transport=httpx.MockTransport(lambda _: next(responses))) as upstream:
        api = MediaWiki(client=upstream, sleep=waits.append)
        monkeypatch.setattr(reader_build, "MediaWiki", lambda _: api)
        with sqlite3.connect(":memory:") as db:
            db.executescript(
                "CREATE TABLE pages(file); INSERT INTO pages VALUES ('Photo.jpg');"
                "CREATE TABLE media(name PRIMARY KEY,data); INSERT INTO media VALUES ('Photo.jpg',NULL);"
            )
            reader_build.enrich(db, None)
            reader_build.enrich(db, None)
            assert db.execute("SELECT status FROM media_checks").fetchone() == ("no_credit",)
            assert waits == [4]


def test_text_results_survive_image_failure():
    def respond(request):
        if request.url.params.get("list") == "search":
            return httpx.Response(200, json={"query": {"search": [{"pageid": 1, "title": "Test"}]}})
        return httpx.Response(429, headers={"Retry-After": "30"})

    app = create_app()
    backend = Mock()
    backend.archived_ids.return_value = set()
    app.dependency_overrides[engine] = lambda: backend
    with (
        TestClient(app) as client,
        httpx.Client(transport=httpx.MockTransport(respond)) as upstream,
    ):
        app.state.wikinews = LiveSearch(MediaWiki(client=upstream))
        response = client.get("/api/search/live", params={"q": "test"})
        assert response.status_code == 200
        assert response.json()["hits"][0]["image"] is None


def test_empty_wikimedia_metadata_array():
    from wikinews_ir.adapters.images import credit

    assert credit({"extmetadata": []}) is None


@pytest.mark.parametrize("code", ["maxlag", "ratelimited", "cirrussearch-too-busy-error"])
def test_retry_json_error_with_http_success(code):
    audit = []
    waits = []
    answers = iter([{"error": {"code": code}}, {"query": {"search": []}}])
    with httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=next(answers)))
    ) as upstream:
        api = MediaWiki(client=upstream, sleep=waits.append)
        assert api.query({"list": "search"}, audit=audit.append) == {"query": {"search": []}}
    assert waits == [1]
    assert [attempt["status_code"] for attempt in audit] == [200, 200]
