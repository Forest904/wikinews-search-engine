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


def test_search_detail_and_empty_state(seeded_backend, browser_page):
    page = browser_page
    with serve(seeded_backend) as url:
        page.goto(url)
        page.get_by_label("Cerca nelle notizie").fill("terremoto")
        page.get_by_role("button", name="Cerca", exact=True).click()
        expect(page.locator("#results li")).to_have_count(1)
        page.get_by_role("link", name="Terremoto in Abruzzo").click()
        expect(page.locator("article")).to_contain_text("soccorsi")
        page.get_by_role("link", name="Torna ai risultati").click()
        expect(page.get_by_label("Cerca nelle notizie")).to_have_value("terremoto")
        expect(page.locator("#results li")).to_have_count(1)
        page.get_by_label("Cerca nelle notizie").fill("zzzznonpresente")
        page.get_by_role("button", name="Cerca", exact=True).click()
        expect(page.get_by_role("status")).to_contain_text("Nessun risultato")
        expect(page.locator("#results li")).to_have_count(0)


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
        page.get_by_label("Profilo di retrieval").select_option("E0")
        expect(page).to_have_url(__import__("re").compile("profile=E0"))
        expect(page.get_by_role("button", name="Successiva")).to_be_enabled()
        page.get_by_role("button", name="Successiva").click()
        expect(page.locator("#page-status")).to_contain_text("Pagina 2")
        page.locator("#results a").click()
        page.get_by_role("link", name="Torna ai risultati").click()
        expect(page.locator("#page-status")).to_contain_text("Pagina 2")
        page.reload()
        expect(page.locator("#page-status")).to_contain_text("Pagina 2")
