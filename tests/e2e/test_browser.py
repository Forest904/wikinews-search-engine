import re
import socket
import threading
import time
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path

import pytest
import uvicorn
from playwright.sync_api import expect, sync_playwright

from wikinews_ir.api.main import create_app
from wikinews_ir.api.routes import engine
from wikinews_ir.config import get_settings
from wikinews_ir.retrieval.engine import RetrievalEngine

pytestmark = pytest.mark.e2e


@contextmanager
def serve(backend):
    app = create_app()
    app.dependency_overrides[engine] = lambda: backend
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        server = uvicorn.Server(uvicorn.Config(app, log_level="warning"))
        thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
        thread.start()
        try:
            deadline = time.monotonic() + 10
            while not server.started:
                if not thread.is_alive() or time.monotonic() > deadline:
                    raise RuntimeError("Test server did not start")
                time.sleep(0.05)
            yield f"http://127.0.0.1:{sock.getsockname()[1]}"
        finally:
            server.should_exit = True
            thread.join(timeout=10)
            assert not thread.is_alive(), "Test server did not stop"


@pytest.fixture
def browser_page(request):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        context = browser.new_context()
        context.tracing.start(screenshots=True, snapshots=True)
        page = context.new_page()
        yield page
        output = Path("output/playwright") / request.node.name
        # Artifacts are kept for every run, including failed assertions.
        output.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(output / "page.png"), full_page=True)
        context.tracing.stop(path=str(output / "trace.zip"))
        browser.close()


@pytest.mark.parametrize("return_link", [".back-link", ".reading-actions"])
def test_search_detail_and_empty_state(seeded_backend, browser_page, return_link):
    page = browser_page
    with serve(seeded_backend) as url:
        page.goto(url)
        page.get_by_label("Cerca nelle notizie").fill("terremoto")
        page.get_by_role("button", name="Cerca", exact=True).click()
        expect(page.locator("#results li")).to_have_count(1)
        page.get_by_role("link", name="Terremoto in Abruzzo").click()
        expect(page.locator("article")).to_contain_text("soccorsi")
        if return_link == ".back-link":
            page.locator("a.back-link").click()
        else:
            page.get_by_role("navigation", name="Navigazione articolo").get_by_role(
                "link", name="Torna ai risultati", exact=True
            ).click()
        expect(page.get_by_label("Cerca nelle notizie")).to_have_value("terremoto")
        expect(page.locator("#results li")).to_have_count(1)
        page.get_by_label("Cerca nelle notizie").fill("zzzznonpresente")
        page.get_by_role("button", name="Cerca", exact=True).click()
        expect(page.get_by_role("status")).to_contain_text("Nessun risultato")
        expect(page.locator("#results li")).to_have_count(0)


def test_semantic_filter_survives_article_and_back(seeded_backend, browser_page, monkeypatch):
    monkeypatch.setenv("SEMANTIC_ENABLED", "1")
    from wikinews_ir import semantic

    def search_fixture(request):
        assert (request.profile, request.year_from, request.year_to) == ("semantic", 2000, 2030)
        # The seeded reader fixtures have no publication dates.
        result = seeded_backend.search(request.model_copy(update={
            "profile": "E1", "year_from": None, "year_to": None,
        }))
        return result.model_copy(update={"profile": "semantic"})

    monkeypatch.setattr(semantic, "search", search_fixture)
    page = browser_page
    with serve(seeded_backend) as url:
        page.goto(url)
        page.get_by_label("Cerca nelle notizie").fill("terremoto")
        page.get_by_role("button", name="Filtri").click()
        page.get_by_label("Modalità di ricerca").select_option("semantic")
        page.get_by_label("Da anno").fill("2000")
        page.get_by_label("Ad anno").fill("2030")
        page.get_by_role("button", name="Cerca", exact=True).click()
        page.get_by_role("link", name="Terremoto in Abruzzo").click()
        expect(page.locator("article")).to_contain_text("soccorsi")
        page.locator("a.back-link").click()
        expect(page.locator("#profile")).to_have_value("semantic")
        expect(page.locator("#results li")).to_have_count(1)


def test_backend_unavailable(browser_page):
    # A bound, non-listening socket reserves a port without accepting connections.
    with socket.socket() as unavailable:
        unavailable.bind(("127.0.0.1", 0))
        backend = RetrievalEngine(replace(
            get_settings(),
            elasticsearch_url=f"http://127.0.0.1:{unavailable.getsockname()[1]}",
            elasticsearch_timeout=0.2,
        ))
        try:
            with serve(backend) as url:
                browser_page.goto(url)
                browser_page.get_by_label("Cerca nelle notizie").fill("calcio")
                with browser_page.expect_response("**/api/search?*") as response:
                    browser_page.get_by_role("button", name="Cerca", exact=True).click()
                assert response.value.status == 503
                expect(browser_page.get_by_role("status")).to_contain_text("non è disponibile")
        finally:
            backend.close()


def test_profile_pagination_and_restored_url(seeded_backend, browser_page):
    page = browser_page
    with serve(seeded_backend) as url:
        page.goto(url + "/?q=italiana&profile=E1&page_size=1")
        expect(page.locator("#results li")).to_have_count(1)
        page.get_by_role("button", name="Filtri").click()
        page.get_by_label("Modalità di ricerca").select_option("E0")
        expect(page).to_have_url(re.compile("profile=E1"))
        page.get_by_role("button", name="Cerca", exact=True).click()
        expect(page).to_have_url(re.compile("profile=E0"))
        expect(page.get_by_role("button", name="Successiva")).to_be_enabled()
        page.get_by_role("button", name="Successiva").click()
        expect(page.locator("#page-status")).to_contain_text("Pagina 2")
        page.locator("#results a").click()
        page.locator("a.back-link").click()
        expect(page.locator("#page-status")).to_contain_text("Pagina 2")
        page.reload()
        expect(page.locator("#page-status")).to_contain_text("Pagina 2")


@pytest.mark.parametrize("profile", ["E2", "E3", "E4"])
def test_advanced_profiles_navigation(seeded_backend, browser_page, profile):
    page = browser_page
    with serve(seeded_backend) as url:
        page.goto(url + f"/?q=italiana&profile={profile}&page_size=1")
        expect(page.get_by_label("Modalità di ricerca")).to_have_value(profile)
        expect(page.locator("#results li")).to_have_count(1)
        expect(page.locator("#results mark").first).to_be_visible()
        page.get_by_role("button", name="Successiva").click()
        expect(page.locator("#page-status")).to_contain_text("Pagina 2")
        page.locator("#results a").click()
        page.locator("a.back-link").click()
        expect(page.locator("#page-status")).to_contain_text("Pagina 2")
        expect(page.get_by_label("Modalità di ricerca")).to_have_value(profile)


def test_phrase_error_and_safe_highlighting(seeded_backend, browser_page):
    page = browser_page
    with serve(seeded_backend) as url:
        page.goto(url + '/?profile=E4')
        page.get_by_label("Cerca nelle notizie").fill('"terremoto')
        page.get_by_role("button", name="Cerca", exact=True).click()
        expect(page.get_by_role("status")).to_contain_text("Chiudere le virgolette")
        page.get_by_label("Cerca nelle notizie").fill('"terremoto in Abruzzo"')
        page.get_by_role("button", name="Cerca", exact=True).click()
        expect(page.locator("#results li")).to_have_count(1)
        expect(page.locator("#results mark").first).to_be_visible()
        # Simulate hostile API text to exercise the actual DOM renderer.
        hostile = '<img src=x onerror="window.injected=true">'
        page.route("**/api/search?*", lambda route: route.fulfill(json={
            "total": 1, "elapsed_ms": 0, "page": 1, "page_size": 10,
            "hits": [{"document_id": "demo-01", "title": hostile, "snippet": hostile,
                      "title_segments": [{"text": hostile, "highlighted": True}],
                      "snippet_segments": [{"text": hostile, "highlighted": False}]}],
        }))
        page.get_by_role("button", name="Cerca", exact=True).click()
        expect(page.locator("#results mark")).to_have_text(hostile)
        expect(page.locator("#results img")).to_have_count(0)
        assert page.evaluate("window.injected") is None


def test_search_history_recovery_and_responsive_layout(seeded_backend, browser_page):
    page = browser_page
    output = Path("output/playwright/polish")
    output.mkdir(parents=True, exist_ok=True)
    with serve(seeded_backend) as url:
        page.set_viewport_size({"width": 1280, "height": 720})
        page.goto(url)
        expect(page.locator("#pagination")).to_be_hidden()
        page.screenshot(path=str(output / "search-home.png"))
        page.get_by_label("Cerca nelle notizie").fill("terremoto")
        page.get_by_role("button", name="Cerca", exact=True).click()
        expect(page.locator("#results a")).to_have_count(1)
        expect(page.locator("#results a").first).to_be_in_viewport()
        expect(page.locator("#status")).to_have_text("1 risultato")
        page.screenshot(path=str(output / "search-results.png"))
        page.get_by_label("Cerca nelle notizie").fill("zzzznonpresente")
        page.get_by_role("button", name="Cerca", exact=True).click()
        expect(page.locator("#status")).to_contain_text("Nessun risultato")
        page.go_back()
        expect(page.get_by_label("Cerca nelle notizie")).to_have_value("terremoto")
        expect(page.locator("#results a")).to_have_count(1)
        page.go_forward()
        expect(page.locator("#status")).to_contain_text("Nessun risultato")
        page.go_back()
        expect(page.locator("#results a")).to_have_count(1)
        page.locator("#results a").click()
        expect(page.locator(".article-body")).to_contain_text("soccorsi")
        page.screenshot(path=str(output / "article.png"))
        page.locator("a.back-link").click()
        expect(page.locator("#results a")).to_have_count(1)
        for width, height in [(1440, 900), (1024, 768), (390, 844), (640, 450)]:
            page.set_viewport_size({"width": width, "height": height})
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            page.screenshot(path=str(output / f"search-{width}.png"))
        page.route("**/api/search?*", lambda route: route.abort())
        page.get_by_role("button", name="Cerca", exact=True).click()
        expect(page.locator("#retry")).to_be_visible()
        expect(page.get_by_label("Cerca nelle notizie")).to_have_value("terremoto")
        page.unroute("**/api/search?*")
        page.get_by_role("button", name="Riprova", exact=True).click()
        expect(page.locator("#results a")).to_have_count(1)
        page.get_by_role("button", name="Filtri").click()
        page.get_by_label("Modalità di ricerca").select_option("E4")
        expect(page.locator("#profile-help")).to_contain_text("virgolette")
        expect(page.locator("#profile option:checked")).to_have_text("Frasi")
        expect(page.locator("#profile-help")).to_contain_text("Profilo E4")


@pytest.mark.parametrize("width", [390, 1280])
def test_live_results_and_navigation(browser_page, width):
    page = browser_page
    page.set_viewport_size({"width": width, "height": 850})
    hit = dict(document_id="42", pageid=42, title="Notizia", snippet="Testo",
               url="https://it.wikinews.org/wiki/Notizia", local_url="/articles/42",
               image=dict(url="https://thumb.wikimedia.org/test.png", width=320, height=240,
                          source="https://commons.wikimedia.org/wiki/File:Test.png",
                          license="Public domain", artist="Autore", license_url=""))
    page.route("https://thumb.wikimedia.org/**", lambda route: route.fulfill(
        content_type="image/svg+xml", body='<svg xmlns="http://www.w3.org/2000/svg"/>'))
    page.route("**/api/search/live?*", lambda route: route.fulfill(json={
        "total": 12, "hits": [hit, {**hit, "document_id": "43", "local_url": None, "image": None}],
        "next_cursor": None if "cursor=" in route.request.url else "next"}))
    backend = RetrievalEngine()
    try:
        with serve(backend) as url:
            page.goto(url)
            page.locator("#filters").click()
            page.locator("[name=year_from]").fill("2005")
            page.locator("#profile").select_option("live")
            expect(page.locator("[name=year_from]")).to_be_disabled()
            page.locator("#q").fill("test")
            page.locator("#q").press("Enter")
            expect(page.locator("#results li")).to_have_count(2)
            expect(page.locator(".live-figure")).to_be_visible()
            expect(page.locator(".result-copy > a").first).to_have_attribute("href", re.compile("/articles/42.*mode=live"))
            expect(page.locator(".result-copy > a").last).to_have_attribute("href", hit["url"])
            page.locator("#next").click()
            expect(page.locator("#page-status")).to_have_text("Pagina 2")
            page.go_back()
            expect(page.locator("#page-status")).to_have_text("Pagina 1")
            page.locator("#filters").click()
            page.locator("#profile").select_option("E0")
            expect(page.locator("[name=year_from]")).to_be_enabled()
            expect(page.locator("[name=year_from]")).to_have_value("2005")
    finally:
        backend.close()
