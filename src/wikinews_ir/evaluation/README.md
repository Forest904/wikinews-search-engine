# Valutare i risultati di ricerca

Per riprodurre il confronto finale, parti dai [risultati e comandi M6-B](../../../docs/evaluation.md#risultati-sperimentali). Per preparare query e giudizi di rilevanza, segui la [guida alla valutazione](../../../docs/evaluation.md).

## Esportare una classifica

`runs.py` esporta ranking E0–E4 con lo stesso RetrievalEngine di API/UI:
`wikinews-ir runs export --queries <queries.jsonl> --output <nuova-directory>`.
Produce file TREC e manifest, con hash, metadati e query senza risultati.
Non legge qrels e non modifica gli score per risolvere le parità: rispettare
rank e tiebreak document_id crescente dichiarati nel manifest.

`benchmark` espone contratti, riconciliazione, pooling, selezione, pacchetti ciechi,
workflow silver in una nuova chat Codex e qrels separati. `portable_validator.py`
viene copiato nel workspace del batch e usa solo la libreria standard Python.
Nessun client API LLM. Documentazione: `docs/evaluation.md`.
Per assegnazioni, revisione e ripristino consultare la [guida operativa](../../../docs/operazioni.md#annotazione). I risultati congelati e i limiti della raccolta sono nella [valutazione](../../../docs/evaluation.md#raccolta).
