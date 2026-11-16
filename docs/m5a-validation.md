# Verifica M5-A — 2026-11-16

**Stato:** infrastruttura implementata e verificata offline su fixture. Nessun
benchmark definitivo, giudizio umano o silver reale prodotto; nessuna acquisizione
Wikimedia live o chiamata API LLM eseguita.

## Riconciliazione reale

Input esplorativo: `evaluation/pilot` nella directory esterna del dump indicata
dal maintainer. Letti esclusivamente topic, candidati e documenti, senza eseguire
script esterni o importare proposte di etichetta.

| Controllo | Esito |
|---|---:|
| Topic adattati come bozze calibration | 4 |
| Coppie analizzate | 48 |
| ID presenti nel corpus M2 | 48 |
| Revisioni corrispondenti | 48 |
| Testi puliti esattamente uguali | 0 |
| Etichette importate | 0 |

Tutte le coppie possono essere riesaminate sul testo M2; nessuna citazione esterna
viene trasferita. Le 48 coppie diagnostiche non sono il pool definitivo multi-run.
La differenza 11.031/11.032 della policy esterna non richiede modifiche al corpus M2.

Fingerprint input esterni:

- Topic: `17a44721e82fe7c5bae18ab33f4e255538bd9e932b5cd1c38c286365cadaed31`.
- Candidati: `f5a1de258094691cafe26f24a59dc304db9d5de812dc48eb769eb3b82b57f220`.
- Documenti: `fedcaf6f014890682ed4c58333bc8e9466aa8be879cf7ecb8b06e7d908e2d309`.
- Corpus M2: `b85295e118431f71b06c56b04a27ca76010f90004eb45d29256ec8bca9443b45`.

Output locale ignorato: `experiments/reports/m5a-reconciliation-v1`, con report
per coppia e manifest. Le bozze adattate sono versionate in
`benchmarks/topics/calibration-draft.jsonl`. La riproduzione usa il comando
`benchmark reconcile-pilot` con directory di output nuova.

## Verifiche automatiche

La suite offline verifica pooling, quote riproducibili, corpus/query incompatibili,
schema/split, workflow Codex autonomo, errori e astensioni, import/export separati e
decisioni gold esplicite. HTTP Wikimedia simulato verifica paginazione, retry,
risultati fuori corpus, duplicati e archivi incompleti. Nessun dato sintetico viene
presentato come giudizio reale.

- `uv run --locked ruff check .`: superato.
- `uv run --locked pytest -m "not integration and not e2e"`: 145 superati, 13 esclusi.
- `git diff --check`: superato.
- Validazione CLI dei quattro topic adattati: superata.

La suite include 20 casi M5-A; rimane un warning di deprecazione Starlette/httpx
già relativo al TestClient. Test Elasticsearch/browser non eseguiti in questa fase;
nessuna modifica ai profili retrieval o alle API di ricerca.

## Limiti e prossimi gate

Rubriche e quote vanno calibrate in M5-C. Il codice non prova che la ricerca live
Wikimedia sarà disponibile: il collaudo live rimane futuro. Il modello della chat
è dichiarato dall'operatore, non verificabile tramite questa pipeline. Il workspace
separato riduce i dati forniti ma non isola tecnicamente gli accessi dell'agente.
I checksum e i controlli sulle citazioni non dimostrano la correttezza semantica.
UI, assegnazioni e adjudication interattiva rimangono M5-B; metriche M6-A.
