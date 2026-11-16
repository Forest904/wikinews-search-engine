# Test di integrazione M0

Avviare Elasticsearch con `docker compose up -d --wait elasticsearch`.
Impostare `RUN_INTEGRATION=1` ed eseguire `uv run --locked pytest tests/integration -q`.
I test verificano health autenticato e rifiuto di credenziali errate, senza creare indici.
Sono esclusi automaticamente dalla suite normale se la variabile non ? impostata.
