# Evaluation — export M3, benchmark M5/M6

`runs.py` esporta ranking E0/E1 con lo stesso RetrievalEngine di API/UI:
`wikinews-ir runs export --queries <queries.jsonl> --output <nuova-directory>`.
Produce file TREC e manifest, con hash, metadati e query senza risultati.
Non legge qrels e non modifica gli score per risolvere le parità: rispettare
rank e tiebreak document_id crescente dichiarati nel manifest.

Restano pianificati topic TREC-like, pooling di run candidate, annotazioni umane e LLM indipendenti,
qrels con provenienza, metriche con ir-measures e report riproducibili.
Non sono ancora presenti giudizi o metriche sperimentali reali.
