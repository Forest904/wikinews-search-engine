# Dal dump agli articoli ricercabili

Per preparare gli articoli ed eseguire la prima indicizzazione, segui il [primo avvio](../../../README.md#primo-avvio). Qui trovi i comandi per controllare i dati e ripetere i singoli passaggi.

`acquisition.py` aggiunge `wikinews-ir corpus prepare`: download dello snapshot
fissato, controllo SHA-256 e preparazione. Archivio e corpus già validi sono
verificati e riusati offline. Opzioni `--raw-dir` e `--output` per percorsi alternativi.

`corpus.py` implementa reader streaming tar.gz/NDJSON, validazione, deduplicazione
SQLite, selezione, cleaning HTML, date, corpus normalizzato e manifest.

```bash
uv run --locked wikinews-ir corpus audit --input data/raw/itwikinews-NS0-20250320-ENTERPRISE-HTML.json.tar.gz --output data/processed/audit-v1
uv run --locked wikinews-ir corpus build --input data/raw/itwikinews-NS0-20250320-ENTERPRISE-HTML.json.tar.gz --output data/processed/m2-v1
```

Output già popolati sono rifiutati. L'audit non pubblica `articles.ndjson` e
restituisce exit code 1 se rileva errori strutturali. Questi comandi non richiedono ES.

`indexer.py` implementa M3: `wikinews-ir index build` valida gli artefatti processed,
costruisce entrambi gli indici E0/E1 con bulk streaming e verifica l'intero contenuto.
Il riuso è verificato; `--rebuild` ricrea esplicitamente le destinazioni configurate.
Indici completi bloccati in scrittura, manifest separati dal corpus; `seed-demo`
utilizza lo stesso indexer ma solo indici demo e fixture sintetiche.

Policy e schema: [dataset.md](../../../docs/dataset.md).
