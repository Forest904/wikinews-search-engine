"""The entire M5-B workflow in independent browser sessions, without Elasticsearch."""

import socket
import threading
import time
from pathlib import Path

import pytest
import uvicorn
from playwright.sync_api import expect, sync_playwright

from wikinews_ir.annotation import connect, create_user, import_packet
from wikinews_ir.annotation_cli import demo_payload
from wikinews_ir.annotation_workflow import activate_block, create_block
from wikinews_ir.api.main import create_app
from wikinews_ir.evaluation.artifacts import encoded, write_bundle

pytestmark = pytest.mark.annotation_e2e


@pytest.fixture
def server(tmp_path, monkeypatch):
    monkeypatch.setenv("ANNOTATION_DB", str(tmp_path / "annotation.sqlite3"))
    monkeypatch.setenv("ANNOTATION_COOKIE_SECURE", "0")
    write_bundle(tmp_path / "packet", "packet", {"packet.json": encoded(demo_payload())})
    with connect(tmp_path / "annotation.sqlite3") as db:
        for name in ("alice", "bob", "carol"):
            create_user(db, name, "password-test", coordinator=name == "alice")
        packet_id = import_packet(db, tmp_path / "packet")
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        app = create_app()
        service = uvicorn.Server(uvicorn.Config(app, log_level="warning"))
        thread = threading.Thread(target=service.run, kwargs={"sockets": [sock]}, daemon=True)
        thread.start()
        deadline = time.monotonic() + 10
        while not service.started:
            if not thread.is_alive() or time.monotonic() > deadline:
                raise RuntimeError("Server non avviato")
            time.sleep(.05)
        try:
            yield f"http://127.0.0.1:{sock.getsockname()[1]}", tmp_path / "annotation.sqlite3", packet_id
        finally:
            service.should_exit = True
            thread.join(timeout=10)
            assert not thread.is_alive()


def sign_in(page, url, name, route="annotate"):
    page.goto(f"{url}/{route}")
    page.get_by_label("Nome utente", exact=True).fill(name)
    page.get_by_label("Password", exact=True).fill("password-test")
    page.get_by_role("button", name="Accedi", exact=True).click()
    expect(page.locator("#workspace")).to_be_visible()


def choose_document(page, document="Pannelli solari nella scuola di Bologna"):
    option = page.locator("#tasks option").filter(has_text=document)
    page.locator("#tasks").select_option(option.get_attribute("value"))
    expect(page.locator("#title")).to_have_text(document)


def cite(page, quote="La scuola"):
    # A real DOM selection exercises browser UTF-16 -> Python Unicode offsets.
    page.locator("#body").evaluate("""(element, quote) => {
      const walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT);
      let node;
      while ((node = walker.nextNode())) {
        const index = node.textContent.indexOf(quote);
        if (index >= 0) {
          const range = document.createRange(); range.setStart(node,index);
          range.setEnd(node,index + quote.length);
          const selection = window.getSelection(); selection.removeAllRanges(); selection.addRange(range);
          return;
        }
      }
      throw new Error('Quote absent');
    }""", quote)
    page.get_by_role("button", name="Aggiungi citazione", exact=False).click()
    expect(page.locator("#evidence")).to_contain_text(quote)


def test_three_users_assignment_judgment_review_export(server):
    url, _, _ = server
    output = Path("output/playwright/annotation")
    output.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        contexts = [browser.new_context(viewport={"width":1440,"height":1100}) for _ in range(3)]
        pages = [context.new_page() for context in contexts]
        errors = []
        for page in pages:
            page.on("pageerror", lambda error: errors.append(str(error)))
        alice, bob, carol = pages
        try:
            sign_in(alice,url,"alice","coordinate")
            alice.locator("#primary-user").select_option("alice")
            alice.locator("#secondary-user").select_option("bob")
            alice.get_by_label("Documenti in doppio").fill("4")
            alice.get_by_role("button",name="Prepara e mostra riepilogo").click()
            expect(alice.locator("#preview-summary")).to_contain_text("4 documenti in doppio")
            alice.get_by_role("button",name="Attiva questo blocco").click()
            expect(alice.locator("#message")).to_contain_text("Blocco attivato")
            alice.goto(url + "/annotate")
            expect(alice.locator("#workspace")).to_be_visible()
            sign_in(bob,url,"bob")
            choose_document(alice)
            choose_document(bob)
            alice.get_by_label("Cerca nel testo",exact=True).fill("scuola")
            expect(alice.locator("#body mark")).to_have_count(1)
            alice.get_by_label("Cerca nel testo",exact=True).fill("")
            cite(alice, "📚")
            cite(alice, "Gli studenti")
            alice.locator('input[name=grade][value="2"]').check()
            alice.get_by_label("Motivazione",exact=True).fill("Il testo descrive un impianto in una scuola.")
            alice.get_by_role("button",name="Salva",exact=True).click()
            expect(alice.locator("#message")).to_have_text("Salvataggio confermato.")
            alice.screenshot(path=str(output / "annotator-desktop.png"),full_page=True)
            assert "Il testo descrive un impianto in una scuola." not in bob.locator("body").inner_text()
            cite(bob)
            bob.locator('input[name=grade][value="0"]').check()
            bob.get_by_label("Motivazione",exact=True).fill("Interpretazione differente, da riesaminare.")
            bob.get_by_role("button",name="Salva",exact=True).click()
            expect(bob.locator("#message")).to_have_text("Salvataggio confermato.")
            alice.goto(url + "/coordinate")
            expect(alice.locator("#total-reviews")).to_have_text("1")
            expect(alice.locator("#reviews select option")).to_have_count(2)  # placeholder + carol
            alice.locator("#reviews select").select_option("carol")
            alice.get_by_role("button",name="Assegna revisione",exact=True).click()
            expect(alice.locator("#message")).to_contain_text("Revisione assegnata")
            sign_in(carol,url,"carol")
            carol.get_by_role("button",name="Revisioni assegnate",exact=False).click()
            expect(carol.locator("#originals")).to_contain_text("Interpretazione differente")
            cite(carol)
            carol.locator('input[name=grade][value="2"]').check()
            carol.get_by_label("Motivazione",exact=True).fill("L'installazione nella scuola è esplicita.")
            carol.get_by_role("button",name="Salva",exact=True).click()
            expect(carol.locator("#message")).to_have_text("Decisione finale salvata.")
            alice.get_by_role("button",name="Aggiorna",exact=True).click()
            expect(alice.locator("#total-finalized")).to_have_text("1")
            alice.screenshot(path=str(output / "coordinator-desktop.png"),full_page=True)
            with alice.expect_download() as info:
                alice.get_by_role("button",name="Scarica archivio gold").click()
            info.value.save_as(str(output / "gold-calibration.zip"))
            assert not errors
        finally:
            browser.close()


def test_resume_failure_conflict_history_and_mobile(server):
    url, path, packet_id = server
    with connect(path) as db:
        prepared = create_block(db,"alice",packet_id,"demo-energia","alice",None,0,"42")
        activate_block(db,"alice",prepared["block"]["id"])
    output = Path("output/playwright/annotation")
    output.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        context = browser.new_context(viewport={"width":1440,"height":1100})
        page = context.new_page()
        try:
            sign_in(page,url,"alice")
            choose_document(page)
            cite(page)
            page.get_by_label("Motivazione",exact=True).fill("Bozza da riprendere")
            page.get_by_role("button",name="Riprendi dopo",exact=True).click()
            expect(page.locator("#message")).to_have_text("Salvataggio confermato.")
            page.reload()
            expect(page.locator("#workspace")).to_be_visible()
            choose_document(page)
            expect(page.get_by_label("Motivazione",exact=True)).to_have_value("Bozza da riprendere")
            expect(page.locator("#evidence")).to_contain_text("La scuola")
            other = context.new_page()
            other.goto(url + "/annotate")
            expect(other.locator("#workspace")).to_be_visible()
            choose_document(other)
            page.locator('input[name=grade][value="2"]').check()
            page.route("**/api/annotation/judgments",lambda route: route.fulfill(status=503,json={"detail":"Errore simulato"}))
            page.get_by_role("button",name="Salva e continua",exact=True).click()
            expect(page.locator("#message")).to_have_text("Errore simulato")
            expect(page.locator("#title")).to_have_text("Pannelli solari nella scuola di Bologna")
            expect(page.get_by_label("Motivazione",exact=True)).to_have_value("Bozza da riprendere")
            page.unroute("**/api/annotation/judgments")
            page.get_by_role("button",name="Salva",exact=True).click()
            expect(page.locator("#message")).to_have_text("Salvataggio confermato.")
            other.locator('input[name=grade][value="1"]').check()
            other.get_by_role("button",name="Salva",exact=True).click()
            expect(other.locator("#message")).to_contain_text("Versione superata")
            page.get_by_text("Cronologia delle mie revisioni",exact=True).click()
            expect(page.locator("#history li")).to_have_count(2)
            page.set_viewport_size({"width":390,"height":844})
            page.screenshot(path=str(output / "annotator-mobile.png"),full_page=True)
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        finally:
            browser.close()
