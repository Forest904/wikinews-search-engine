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


def cite(page, quote="La scuola", button="Aggiungi citazione"):
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
    page.get_by_role("button", name=button, exact=False).click()
    expect(page.locator("#evidence")).to_contain_text(quote)


def test_collapsible_timer_and_coordinator_without_discussion(server):
    url, path, packet_id = server
    with connect(path) as db:
        preview = create_block(db, "alice", packet_id, "demo-energia", "alice", "bob", 4, "pilot", "carol")
        activate_block(db, "alice", preview["block"]["id"])
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        contexts = [browser.new_context() for _ in range(3)]
        pages = [context.new_page() for context in contexts]
        errors = []
        for page in pages:
            page.on("pageerror", lambda error: errors.append(str(error)))
        try:
            for page, user in zip(pages, ("alice", "bob", "carol"), strict=True):
                sign_in(page, url, user)
            alice = pages[0]
            alice.locator("#timer-panel > summary").click()
            alice.get_by_role("button", name="Avvia / riprendi").click()
            expect(alice.get_by_label("Tempo operativo")).to_contain_text("Timer attivo")
            alice.get_by_role("button", name="Pausa", exact=True).click()
            expect(alice.get_by_label("Tempo operativo")).to_contain_text("Timer in pausa")
            alice.get_by_label("Fase del timer").select_option("annotation")
            alice.get_by_role("button", name="Avvia / riprendi").click()
            expect(alice.get_by_label("Tempo operativo")).to_contain_text("Timer attivo: Compilazione")
            alice.locator("#timer-panel > summary").click()
            expect(alice.get_by_label("Tempo operativo")).to_contain_text("Timer attivo: Compilazione")
            expect(alice.get_by_role("button", name="Pausa", exact=True)).to_be_hidden()
            alice.evaluate("Object.defineProperty(document, 'hidden', {value:true, configurable:true}); document.dispatchEvent(new Event('visibilitychange'))")
            expect(alice.get_by_label("Tempo operativo")).to_contain_text("Timer in pausa")
            alice.reload()
            expect(alice.get_by_label("Tempo operativo")).to_contain_text("Timer in pausa")
            coordinator = contexts[0].new_page()
            coordinator.goto(url + "/coordinate")
            expect(coordinator.locator("#open-discussion")).to_have_count(0)
            expect(coordinator.get_by_text("Discussione del pilot", exact=True)).to_have_count(0)
            for page in pages:
                for i in range(4):
                    page.locator("#tasks").select_option(str(i))
                    page.locator("#rationale").fill("Da discutere durante la calibrazione.")
                    page.get_by_role("button", name="Astieniti", exact=True).click()
                    expect(page.locator("#current-status")).to_have_text("Astensione")
            assert not errors
        finally:
            for context in contexts:
                context.close()
            browser.close()
    with connect(path) as db:
        assert db.execute("SELECT count(*) FROM timing WHERE complete=1").fetchone()[0] == 2
        assert db.execute("SELECT count(*) FROM judgments").fetchone()[0] == 12
        assert db.execute("SELECT count(*) FROM decisions").fetchone()[0] == 0


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
            alice.get_by_role("link", name="Assegnazioni", exact=True).click()
            expect(alice.locator("#prepared-blocks")).not_to_have_attribute("open", "")
            alice.locator("#primary-user").select_option("alice")
            alice.locator("#secondary-user").select_option("bob")
            alice.get_by_label("Documenti in doppio").fill("4")
            alice.get_by_role("button",name="Prepara e mostra riepilogo").click()
            expect(alice.locator("#preview-summary")).to_contain_text("4 documenti in doppio")
            expect(alice.locator("#prepared-blocks")).to_have_attribute("open", "")
            expect(alice.locator("#blocks-count")).to_have_text("1 totali · 1 bozze")
            expect(alice.locator("#blocks .new-block")).to_have_count(1)
            alice.screenshot(path=str(output / "assignments-desktop.png"), full_page=True)
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
            alice.get_by_role("link", name="Revisioni", exact=True).click()
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
            alice.get_by_role("link", name="Panoramica", exact=True).click()
            alice.screenshot(path=str(output / "coordinator-desktop.png"),full_page=True)
            alice.get_by_role("link", name="Esportazione", exact=True).click()
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


def test_desktop_context_citation_validation_and_responsive_surfaces(server):
    url, path, packet_id = server
    with connect(path) as db:
        block = create_block(db, "alice", packet_id, "demo-energia", "alice", None, 0, "layout")
        activate_block(db, "alice", block["block"]["id"])
    output = Path("output/playwright/polish")
    output.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        try:
            page.goto(url + "/annotate")
            expect(page.locator("#login-panel")).to_be_visible()
            page.screenshot(path=str(output / "login.png"))
            page.get_by_role("button", name="Mostra", exact=True).click()
            expect(page.locator("#login-password")).to_have_attribute("type", "text")
            page.get_by_role("button", name="Nascondi", exact=True).click()
            sign_in(page, url, "alice")
            choose_document(page)
            for width, height in [(1440, 900), (1280, 720), (1024, 768), (390, 844)]:
                page.set_viewport_size({"width": width, "height": height})
                page.evaluate("window.scrollTo(0, 0)")
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                if width >= 1280:
                    expect(page.locator("#title")).to_be_in_viewport()
                    expect(page.locator(".grade-options")).to_be_in_viewport()
                    topic = page.locator("#topic-panel").bounding_box()
                    article = page.locator("#article-panel").bounding_box()
                    judgment = page.locator("#judgment-panel").bounding_box()
                    assert topic["y"] < article["y"]
                    assert article["width"] > judgment["width"] * 1.7
                page.screenshot(path=str(output / f"annotation-{width}.png"))
            page.set_viewport_size({"width": 1440, "height": 900})
            # Closing the criteria must not discard the topic or alter the task.
            page.locator("#topic-details > summary").click()
            expect(page.locator("#topic-need")).to_be_visible()
            page.get_by_role("button", name="Salva", exact=True).click()
            expect(page.locator("#grade-error")).to_be_visible()
            expect(page.locator("#evidence-error")).to_be_visible()
            expect(page.locator("#rationale-error")).to_be_visible()
            page.get_by_label("Cerca nel testo", exact=True).fill("scuola")
            page.get_by_role("button", name="Occorrenza successiva").click()
            expect(page.locator("#find-count")).to_have_text("1 di 1 occorrenze")
            cite(page, "scuola", button="Cita il passaggio")
            cite(page, "📚", button="Cita il passaggio")
            page.locator('input[name=grade][value="2"]').check()
            page.get_by_label("Motivazione", exact=True).fill("Installazione descritta nella scuola.")
            page.get_by_role("button", name="Salva", exact=True).click()
            expect(page.locator("#judgment-feedback")).to_have_text("Salvataggio confermato.")
            page.reload()
            expect(page.locator("#evidence li")).to_have_count(2)
            # Simulate 200% layout zoom using half the desktop CSS viewport.
            page.set_viewport_size({"width": 640, "height": 450})
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            page.get_by_role("link", name="Giudizio", exact=True).click()
            expect(page.locator("#judgment-heading")).to_be_in_viewport()
            page.screenshot(path=str(output / "annotation-zoom.png"))
            assert not errors
        finally:
            browser.close()


def test_coordinator_sections_preserve_draft_and_export_confirmation(server):
    url, _, _ = server
    output = Path("output/playwright/polish")
    output.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        try:
            sign_in(page, url, "alice", "coordinate")
            page.get_by_role("link", name="Assegnazioni", exact=True).click()
            page.get_by_label("Documenti in doppio").fill("2")
            page.get_by_role("link", name="Revisioni", exact=True).click()
            page.go_back()
            expect(page.get_by_label("Documenti in doppio")).to_have_value("2")
            expect(page.locator("#prepared-blocks")).not_to_have_attribute("open", "")
            page.screenshot(path=str(output / "assignments-collapsed.png"), full_page=True)
            page.get_by_role("link", name="Esportazione", exact=True).click()
            page.get_by_label("Suddivisione del benchmark").select_option("test")
            requests = []
            page.on("request", lambda request: requests.append(request.url) if "/exports" in request.url else None)
            page.get_by_role("button", name="Scarica archivio gold").click()
            expect(page.locator("#esportazione .section-feedback")).to_contain_text("Conferma il rilascio")
            assert requests == []
            page.screenshot(path=str(output / "export-confirmation.png"))
            page.set_viewport_size({"width": 390, "height": 844})
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            page.screenshot(path=str(output / "coordinator-mobile.png"), full_page=True)
            other = browser.new_page()
            sign_in(other, url, "bob")
            other.goto(url + "/coordinate")
            expect(other.locator("#access-denied")).to_be_visible()
            expect(other.locator("#workspace")).to_be_hidden()
        finally:
            browser.close()


def test_expired_session_retry_keeps_draft_and_identity(server):
    url, path, packet_id = server
    with connect(path) as db:
        block = create_block(db, "alice", packet_id, "demo-energia", "alice", None, 0, "session")
        activate_block(db, "alice", block["block"]["id"])
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        context = browser.new_context()
        page = context.new_page()
        try:
            sign_in(page, url, "alice")
            choose_document(page)
            cite(page)
            page.locator('input[name=grade][value="2"]').check()
            page.get_by_label("Motivazione", exact=True).fill("Giudizio conservato durante la nuova autenticazione.")
            context.clear_cookies()
            page.get_by_role("button", name="Salva", exact=True).click()
            expect(page.locator("#save-state")).to_contain_text("Sessione scaduta")
            other = context.new_page()
            sign_in(other, url, "bob")
            page.get_by_role("button", name="Salva", exact=True).click()
            expect(page.locator("#judgment-feedback")).to_contain_text("altro account")
            expect(page.locator("#rationale")).to_have_value("Giudizio conservato durante la nuova autenticazione.")
            context.clear_cookies()
            sign_in(other, url, "alice")
            page.get_by_role("button", name="Salva", exact=True).click()
            expect(page.locator("#judgment-feedback")).to_have_text("Salvataggio confermato.")
        finally:
            browser.close()
    with connect(path) as db:
        assert db.execute("SELECT count(*) FROM judgments").fetchone()[0] == 1
