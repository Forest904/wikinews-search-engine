# Verificare la ricerca con Elasticsearch

Dalla radice del progetto, usa un cluster locale di test e il file `.env` preparato durante il [primo avvio](../../README.md#primo-avvio).

Avviare Elasticsearch con `docker compose up -d --wait elasticsearch`.
Impostare `RUN_INTEGRATION=1` ed eseguire `uv run --locked pytest tests/integration -q`.
I test verificano health autenticato, rifiuto di credenziali errate, ricerca BM25,
lookup articolo, indice mancante e caricamento idempotente delle cinque fixture.
M3 verifica inoltre analyzer standard/italian, tiebreak, paginazione, indici
immutabili, corpus alterati e export TREC identico dopo rebuild.
Ogni test retrieval crea due indici `test-m3-<famiglia>-<uuid>` e li elimina nel teardown;
non modifica l'indice demo configurato. Non eseguire contro un cluster di produzione.
Sono esclusi automaticamente dalla suite normale se la variabile non è impostata.

I test in `tests/e2e` richiedono separatamente `RUN_E2E=1` e Chromium installato
con `uv run --locked playwright install chromium`. Avviano un server su porta
libera e verificano ricerca, dettaglio, ritorno, empty state e backend non disponibile.
Gli artefatti diagnostici finiscono in `output/playwright/`.
