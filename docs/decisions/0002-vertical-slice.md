# ADR 0002 — Vertical slice M1

Data: 2026-11-16. Stato: implementata e verificata localmente.

## Decisioni

- Conservare il percorso Jinja2 + JavaScript → API → Elasticsearch già presente.
  `/search` con rendering server rimane una possibilità futura, non parte di M1.
- Contratto Python: `search(SearchRequest) -> SearchResponse`, con validazione
  condivisa e normalizzazione della query. Il precedente contratto Python a
  keyword viene sostituito; il contratto HTTP di ricerca rimane compatibile.
- Dettaglio via `get_article(document_id) -> Article`, esposto come JSON e HTML.
  Schema articolo minimo; revisione, provenienza del dump e date spettano a M2.
- Conservare cinque fixture sintetiche e mapping standard; nessun tuning del
  ranking, paginazione, highlight, filtro data o profilo E0/E1 in questa fase.
- Il seed rimane un comando da checkout e accetta impostazioni esplicite per
  l'isolamento dei test. Non cancella gli altri documenti dell'indice di destinazione.
- Playwright Python/Chromium per E2E, senza build Node. Test backend e browser
  esplicitamente abilitabili, con indici univoci eliminati nel teardown e porte libere.

## Evidenze locali

- `uv run --locked ruff check .`: superato.
- Suite completa con `RUN_INTEGRATION=1 RUN_E2E=1`: **56 test superati**.
- Verificati ricerca browser `terremoto → demo-01`, ricerca nel corpo, dettaglio,
  ritorno con query conservata, zero risultati e risposta reale 503 su backend assente.
- Verificati uso Python diretto, seed ripetuto con conteggio invariato e distinzione
  fra articolo mancante e indice mancante su Elasticsearch autenticato 9.5.6.
- Rimane il warning preesistente di deprecazione Starlette/TestClient su httpx.

## CI

La matrice unit test/lint Ubuntu e Windows rimane attiva. Aggiunto un job Ubuntu
con Elasticsearch autenticato e Chromium, con upload diagnostico su errore.
Il nuovo job non è stato eseguito da remoto durante questa implementazione:
il suo esito andrà controllato dopo il push. Non sono stati creati commit o release.
