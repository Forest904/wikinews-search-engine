# Ingestion — M2

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
restituisce exit code 1 se rileva errori strutturali. Nessun comando richiede ES.
Il bulk indexing del corpus reale appartiene a M3; `seed-demo` resta separato.

Policy e schema: [dataset.md](../../../docs/dataset.md).
