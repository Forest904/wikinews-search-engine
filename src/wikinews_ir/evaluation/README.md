# Evaluation — export M3/M4 e infrastruttura M5-A

`runs.py` esporta ranking E0–E4 con lo stesso RetrievalEngine di API/UI:
`wikinews-ir runs export --queries <queries.jsonl> --output <nuova-directory>`.
Produce file TREC e manifest, con hash, metadati e query senza risultati.
Non legge qrels e non modifica gli score per risolvere le parità: rispettare
rank e tiebreak document_id crescente dichiarati nel manifest.

`benchmark` espone contratti, riconciliazione, pooling, selezione, pacchetti ciechi,
workflow silver in una nuova chat Codex e qrels separati. `portable_validator.py`
viene copiato nel workspace del batch e usa solo la libreria standard Python.
Nessun client API LLM. Documentazione: `docs/evaluation.md`.
La UI M5-B è disponibile in `/annotate` e `/coordinate`, con guida in `docs/annotation.md`.
Importate le prime 24 silver reali di calibrazione (GPT-6.0-Astra dichiarato):
diario in `docs/m5c-validation.md`. Raccolta di produzione, confronto umano/silver,
metriche con ir-measures e report sperimentali restano successivi.
