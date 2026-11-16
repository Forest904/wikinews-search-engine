# Test di integrazione M0/M1

Avviare Elasticsearch con `docker compose up -d --wait elasticsearch`.
Impostare `RUN_INTEGRATION=1` ed eseguire `uv run --locked pytest tests/integration -q`.
I test verificano health autenticato, rifiuto di credenziali errate, ricerca BM25,
lookup articolo, indice mancante e caricamento idempotente delle cinque fixture.
Ogni test retrieval crea un indice `test-m1-<uuid>` e lo elimina nel teardown;
non modifica l'indice demo configurato. Non eseguire contro un cluster di produzione.
Sono esclusi automaticamente dalla suite normale se la variabile non è impostata.

I test in `tests/e2e` richiedono separatamente `RUN_E2E=1` e Chromium installato
con `uv run --locked playwright install chromium`. Avviano un server su porta
libera e verificano ricerca, dettaglio, ritorno, empty state e backend non disponibile.
Gli artefatti diagnostici finiscono in `output/playwright/`.
