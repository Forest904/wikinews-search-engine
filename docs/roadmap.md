# Roadmap end-to-end — Wikinews Search Engine

**Versione documento:** 0.1.1 · **Data:** 2026-11-16 · **Stato:** piano approvato come sequenza di riferimento

**Documenti correlati:** [PRD](./prd.md) · [Architettura](./architeture.md)

## 1. Finalità e regole di pianificazione

Portare il progetto **da repository vuoto alla consegna completa** dell'Homework 4: ricerca Web sul dump Wikinotizie, test rigorosi, codice GitHub installabile, presentazione di circa 20 minuti e demo live.

Non è stata indicata una data di consegna; la roadmap è organizzata per **fasi, dipendenze e criteri di uscita**, non per date inventate. Non vengono attribuite responsabilità a persone non definite. Le stime dimensionali (40 topic, ~600 gold, ~1.200 silver) sono target iniziali, non vincoli di completamento se il pilot mostra un diverso fabbisogno.

Regole di esecuzione:

- Ogni fase produce un artefatto verificabile, non soltanto codice scritto.
- Prima un percorso end-to-end minimale, poi qualità dati, poi ranking avanzato, poi studio sperimentale.
- La progettazione del benchmark inizia presto; **il test set rimane riservato**.
- Nessuna nuova feature *Could* prima del completamento dei *Must*.
- Ogni cambiamento di corpus, indice, profilo o protocollo genera una versione/manifest identificabile.

## 2. Quadro generale delle milestone

| Milestone | Risultato dimostrabile | Dipendenze | Gate di uscita |
|---|---|---|---|
| M0 — Repo e tecnologia | Progetto Python, Compose, lint, test | Nessuna | Completato: avvio ambiente e CI base verificati |
| M1 — Vertical slice | UI → API → Elasticsearch → risultati su fixture | M0 | Completato localmente: ricerca browser e Python su fixture |
| M2 — Corpus pipeline | Dump letto, ripulito, deduplicato e manifestato | M0 | Completato localmente: 11.032 articoli e build riproducibili |
| M3 — Baseline completa | E0/E1 con corpus reale, API/UI stabile | M1, M2 | Completato localmente: 11.032 articoli per indice e run identiche dopo rebuild |
| M4 — Retrieval avanzato | E2/E3/E4 e possibili estensioni | M3 | Profili distinti e testati, senza regressioni critiche |
| M5 — Benchmark | Topic, rubriche, split, pooling, gold/silver | M3, M4 parziale | Qrels e pool tracciabili; qualità annotazione controllata |
| M6 — Esperimenti finali | Metriche, confronti, error analysis | M4, M5 | Test gold usato una volta secondo protocollo congelato |
| M7 — Release accademica | GitHub, README, slide, demo live | M6 | Installazione pulita e presentazione provate |

**Parallelismo consentito:** dopo M1, la preparazione dei topic e delle linee guida può avanzare insieme al preprocessing. Il pooling definitivo, invece, dipende dalle run candidate disponibili e dall'identità stabile dei documenti.

## 3. Fase M0 — Bootstrap del repository

**Obiettivo:** avere un progetto coerente, installabile e testabile prima di sviluppare le feature.

### Attività

- [x] Creare repository GitHub `wikinews-search-engine` (nome di lavoro) e licenza del codice appropriata.
- [x] Creare struttura `src/wikinews_ir`, `tests`, `configs`, `data`, `benchmarks`, `experiments`, `docs`.
- [x] Inserire i tre documenti iniziali in `docs/` e collegarli dal README.
- [x] Inizializzare `pyproject.toml`, ambiente Python 3.12, `uv.lock` e configurazione Ruff/pytest.
- [x] Scegliere e fissare una patch Elasticsearch 9.x e client Python compatibile; registrare la decisione.
- [x] Creare `compose.yaml` con Elasticsearch single-node, volume persistente, health check e sicurezza locale.
- [x] Creare `.env.example`, `.gitignore`, Dockerfile minimo e Makefile con target iniziali.
- [x] Implementare app FastAPI minimale con `GET /api/health` e pagina iniziale di servizio.
- [x] Attivare GitHub Actions per lint e unit test su fixture minime.

**Stato: M0 completata (2026-11-16).** Tutti i criteri di uscita sono soddisfatti:
installazione da lockfile, collaudo Docker e health, lint e test locali, CI GitHub
Actions superata (esito remoto confermato dal maintainer). Evidenze e decisioni in
[ADR 0001](decisions/0001-bootstrap.md). M1 successivamente completata: vedere la sezione seguente.

### Deliverable

Repository versionato; `README.md` iniziale; ambiente installabile; servizio Elasticsearch e app avviabili; CI essenziale.

### Exit criteria

1. Un ambiente pulito riesce a installare dipendenze da lockfile.
2. Docker Compose avvia Elasticsearch e il client applicativo si connette con credenziali configurate.
3. `/api/health` distingue correttamente componente pronto e backend non raggiungibile.
4. Lint e test basilari passano localmente e in CI.

## 4. Fase M1 — Vertical slice end-to-end

**Obiettivo:** verificare subito la comunicazione completa tra browser, FastAPI ed Elasticsearch, su dati controllati.

### Attività

- [x] Preparare 5–20 documenti **fixture** sintetici o campione riutilizzabile con provenienza nota.
- [x] Definire un mapping semplice titolo/corpo e indicizzare le fixture.
- [x] Implementare `SearchRequest`, `SearchHit`, `SearchResponse` e `RetrievalEngine`.
- [x] Implementare query builder BM25 di base; validare i parametri.
- [x] Esporre `/api/search` e `/api/articles/{document_id}`.
- [x] Creare form Jinja2 e lista risultati con titolo, snippet, link e empty state.
- [x] Eseguire test end-to-end e gestione di Elasticsearch non disponibile.

### Exit criteria

Una query digitata nel browser recupera dal motore Elasticsearch il risultato atteso su fixture; lo stesso `RetrievalEngine` può essere chiamato da Python senza browser. La vertical slice deve funzionare **prima** della pipeline definitiva del dump.

**Stato: M1 completata e verificata localmente (2026-11-16).**
Ricerca browser e uso Python verificati con Elasticsearch reale; 56 test superati,
inclusi E2E Chromium. Il nuovo job CI remoto resta da verificare dopo il push.
Decisioni ed evidenze in [ADR 0002](decisions/0002-vertical-slice.md).

## 5. Fase M2 — Corpus audit, ingestion e data quality

**Obiettivo:** trasformare lo snapshot fornito in un corpus ricercabile, documentato e versionato.

### Attività

- [x] Acquisire il file del 20/03/2025 nella cartella ignorata `data/raw/`; verificare il checksum SHA-256.
- [x] Implementare reader streaming archivio/JSON con validazione dello schema osservato.
- [x] Riprodurre e verificare i conteggi dell'audit preliminare: 12.261 record, 12.213 identificativi distinti, categoria `Pubblicati` da verificare.
- [x] Definire policy di ammissibilità: namespace, lingua, categoria `Pubblicati`, pagine speciali/redirect e casi incerti.
- [x] Definire policy deterministica di deduplicazione e selezione revisione (`identifier`, `version.identifier`).
- [x] Analizzare campioni di HTML prima/dopo cleaning: navigazione, template, fonti, tabelle e testo giornalistico.
- [x] Implementare cleaner testato su casi rappresentativi e casi limite.
- [x] Validare l'estrazione di date e distinguere pubblicazione, evento e metadati editoriali; mantenere `null` quando incerta.
- [x] Produrre `processed` e manifest con righe lette, tenute, scartate per causa, checksum e versione pipeline.
- [x] Eseguire audit post-processing: ID univoci, testi vuoti/corti, lunghezze anomale, sample review e conteggi.
- [x] Documentare scelte e limiti in `docs/dataset.md` (da creare in questa fase).

### Exit criteria

Ogni documento processed ha ID stabile, revisione, titolo, testo, URL e provenienza. Il numero finale di documenti è giustificato dagli scarti. La stessa versione della pipeline sullo stesso dump produce contenuti equivalenti e identificabili.

**Stato: M2 completata e verificata localmente (2026-11-16).**
Il percorso autonomo è disponibile con `uv run --locked wikinews-ir corpus prepare`:
download con checksum atteso, preparazione e riuso verificato degli artefatti.
12.261 record riconciliati in 48 revisioni superate, 1.181 esclusi e 11.032 articoli.
Due build indipendenti producono gli stessi hash; campione di 40 pagine revisionato.
Ruff superato, 72 test superati e 6 integration/E2E saltati nella verifica offline.
CI remota da verificare dopo il push. Policy, checksum e limiti in
[dataset.md](dataset.md), [revisione campione](dataset-review.md) e
[ADR 0003](decisions/0003-corpus-pipeline.md). Indicizzazione del corpus reale in M3.

## 6. Fase M3 — Baseline sul corpus reale

**Obiettivo:** rendere operativo il sistema completo sul corpus preparato e fissare le baseline di recupero.

### Attività

- [x] Creare mapping e configurazioni versionate per `wikinews_standard_v1` e `wikinews_italian_v1`.
- [x] Implementare indicizzazione bulk idempotente, controllo di conteggio ed esito.
- [x] Introdurre profili `E0` (standard BM25) e `E1` (italian BM25).
- [x] Realizzare ricerca su titolo/corpo, paginazione e dettaglio articolo.
- [x] Aggiungere tiebreak deterministico per ranking sperimentali e metadata indice/profilo nelle risposte.
- [x] Misurare tempi indicizzazione, conteggi e latenza orientativa sul target di demo.
- [x] Verificare qualità di alcuni risultati manualmente e documentare errori di ingestion distinguendoli da problemi di ranking.

### Exit criteria

Il dump assegnato è cercabile dalla Web UI. E0 ed E1 interrogano lo stesso corpus logico; esiste una procedura ripetibile per ricostruire gli indici. Nessuna modifica al ranking viene spacciata per miglioramento senza benchmark.

**Stato: M3 completata e verificata localmente (2026-11-16).**
Entrambi gli indici contengono gli stessi 11.032 articoli M2. UI E0/E1, paginazione,
dettaglio, export TREC e ricostruzione sono verificati. Hash delle run identici
prima e dopo rebuild. Limiti del cleaning distinti dal ranking nel
[report M3](m3-validation.md); decisioni in [ADR 0004](decisions/0004-baseline-corpus.md).
CI remota da verificare dopo il push.

## 7. Fase M4 — Ricerca classica avanzata

**Obiettivo:** introdurre le feature selezionate, ciascuna con configurazione indipendente e test.

### Attività

- [ ] Implementare `E2`: boosting del titolo rispetto al corpo; parametro configurabile.
- [ ] Implementare `E3`: fuzzy matching controllato; scegliere se basso boost, fallback o entrambe le varianti testate.
- [ ] Implementare `E4`: phrase search; chiarire semantica delle virgolette e comportamento UI.
- [ ] Definire e, se utile, implementare `E5`: espansione con sinonimi controllati (opzionale).
- [ ] Valutare miglioramenti UI: highlight e filtro per intervallo date **solo** quando affidabile.
- [ ] Scrivere test unitari del query builder e test integrazione con coppie query-documento difficili.
- [ ] Evitare la combinazione indiscriminata di feature: E3/E4/E5 devono confrontarsi singolarmente con E2.

### Exit criteria

Ogni profilo produce risultati e run con ID/versione riconoscibili. Le feature non interrompono la UI baseline; eventuali regressioni sono misurabili e documentate. La selezione del profilo finale **non** usa il test gold.

## 8. Fase M5 — Benchmark e ground truth multi-sorgente

**Obiettivo:** completare il protocollo che consente di valutare ranking e affidabilità delle etichette.

### M5.1 Definizione topic e rubriche

- [ ] Formalizzare formato topic: query, information need, inclusioni/esclusioni, tipologia, tema, periodo, famiglia evento.
- [ ] Costruire **pilot di 4 topic**, uno per tipologia, usando strategia ibrida corpus/user-driven.
- [ ] Testare la rubrica `0/1/2` e la procedura di astensione su coppie reali, correggendo ambiguità.
- [ ] Portare il benchmark al target di **40 topic**: 10 evento, 10 tema, 10 entità, 10 multi-vincolo.
- [ ] Stratificare temi e periodi; non creare query copiate automaticamente dai titoli delle notizie.
- [ ] Congelare split **24 development / 16 test** per famiglie, evitando eventi quasi duplicati tra set.
- [ ] Registrare varianti con refusi come stress test associati al topic originale, non topic indipendenti.

### M5.2 Candidate generation e pooling

- [ ] Eseguire run E0–E4 con top-k documentato su tutti i topic e salvarle in formato TREC.
- [ ] Realizzare adapter per ricerca Wikinotizie e salvare ranking con timestamp e parametri.
- [ ] Mappare risultati esterni al `document_id` del dump; registrare quelli assenti dallo snapshot.
- [ ] Unire e deduplicare i candidati per topic, preservando provenienza/rank delle run.
- [ ] Definire budget e quote di campionamento **prima** di guardare i giudizi.
- [ ] Registrare numero di candidati, copertura per run e casi non mappati.

### M5.3 Annotazione e controllo qualità

- [ ] Implementare schema unificato per giudizi, motivazioni, evidenza e metadati dell'annotatore.
- [ ] Eseguire LLM-as-a-Judge **offline** (modello configurabile, es. GPT Astra) su pool selezionati; validare output e astensioni.
- [ ] Annotare manualmente gold su parte development e **tutti i topic di test**, con policy di campionamento esplicita.
- [ ] Applicare gli stessi criteri e il medesimo testo pulito a giudici umani e LLM.
- [ ] Nascondere origine/rank e giudizi dell'altro valutatore a ciascun annotatore.
- [ ] Controllare qualità con doppie annotazioni dove possibile, revisione di disaccordi e gestione esplicita di `unjudged`.
- [ ] Versionare separatamente gold e silver, con checksum e protocolli del benchmark.

### Exit criteria

Esistono topic, split, candidate pools, qrels gold e silver separati, ranking Wikinotizie come **run esterna** e manifest di provenienza. Il benchmark è utilizzabile da script senza consultazione live del Web/LLM. Non è necessario rispettare numeri arbitrari se il pilot giustifica un diverso budget; la scelta va documentata.

## 9. Fase M6 — Valutazione, selezione e analisi degli errori

**Obiettivo:** dimostrare sperimentalmente quali configurazioni funzionano meglio e quanto è affidabile il giudice automatico.

### Attività

- [ ] Implementare report `ir-measures`: nDCG@10, P@5 (soglia di rilevanza dichiarata), eventuale MRR@10.
- [ ] Calcolare metriche per query e medie sulle run usando **development gold** per selezione/tuning.
- [ ] Effettuare confronto E0 → E1 → E2 e ablation di E3/E4/(E5).
- [ ] Misurare effetto delle varianti di refuso e delle query più vincolate.
- [ ] Quantificare copertura dei giudizi in top-k e sensibilità agli unjudged; non interpretare recall completo come noto.
- [ ] Confrontare gold e silver sulle **stesse** coppie: matrice di confusione, macro-F1, weighted kappa e disaccordi.
- [ ] Determinare se silver produce lo stesso ordinamento dei sistemi del gold; descrivere eventuale bias del giudice.
- [ ] Congelare profilo candidato e protocollo di analisi **prima** di aprire il test gold.
- [ ] Eseguire valutazione finale su 16 test topic e registrare risultati, limiti e interpretazione.
- [ ] Salvare run, manifest, tabelle, grafici e testo di error analysis; non scegliere ex post la metrica più favorevole.

### Exit criteria

Risultati riproducibili e interpretati correttamente: miglioramenti/regressioni documentati; confronto gold/silver; analisi degli errori; nessuna affermazione forte basata su pool incompleti o differenze statisticamente non supportate.

## 10. Fase M7 — Consegna, presentazione e demo

**Obiettivo:** soddisfare integralmente la consegna del professore con un repository leggibile e una dimostrazione affidabile.

### M7.1 Release repository

- [ ] Aggiornare `README.md`: panoramica, requisiti hardware/software, setup, download dump, `.env`, `make up`, ingest, run, test, benchmark, troubleshooting.
- [ ] Documentare architettura reale e decisioni finali; rimuovere voci obsolete dal blueprint.
- [ ] Aggiornare `docs/dataset.md`, `docs/evaluation.md` e ADR effettivamente necessari.
- [ ] Inserire link alla fonte e indicazioni corrette su copyright/licenza dei contenuti; non committare l'intero dump.
- [ ] Verificare che non siano presenti segreti, file temporanei, indici Elasticsearch o gigabyte di raw data.
- [ ] Pubblicare release/tag e commit di riferimento dei risultati sperimentali.
- [ ] Provare installazione da clone pulito con i soli prerequisiti dichiarati.

### M7.2 Presentazione di circa 20 minuti

Struttura orientativa, da adattare ai risultati disponibili:

| Segmento | Durata indicativa | Contenuto |
|---|---:|---|
| Problema e vincoli | 2 min | Homework, corpus, obiettivi |
| Sfide dati/architettura | 4 min | Parsing, pulizia, index design, stack |
| Retrieval e scelte | 4 min | BM25, analyzer, boosting, fuzzy/phrase |
| Ground truth e metodologia | 5 min | Pooling, gold/silver, baseline esterna, metriche |
| Risultati e limiti | 5 min | Tabelle/grafici, trade-off, errori |

Totale ~20 minuti; **nessun codice nelle slide**, come richiesto. La demo live è un deliverable separato e va collocata nei tempi richiesti dal docente, non forzatamente dentro questi 20 minuti.

### M7.3 Demo live e contingency

- [ ] Avviare Elasticsearch con indice già persistito, backend e UI prima della prova.
- [ ] Preparare 3–5 query rappresentative (semplice, avanzata, typo/phrase, no-results), senza selezionarle per simulare metriche.
- [ ] Verificare `/api/health`, conteggio indice, funzionamento dei link e filtro data se presente.
- [ ] Mostrare almeno un confronto controllato di profilo, senza dipendere da chiamate LLM in tempo reale.
- [ ] Preparare istruzioni di ripristino rapide per container/indice/app.
- [ ] Fare prova completa su macchina e rete della presentazione, preferendo demo che funzioni offline dal sito Wikinotizie e dai servizi LLM.

### Exit criteria / Definition of Done

Il progetto è **done** soltanto quando tutti i requisiti HW-01..HW-06 del [PRD](./prd.md) sono verificati, il repository può essere seguito da terzi, la ricerca Web lavora sul dump assegnato, gli esperimenti sono riproducibili, la presentazione è pronta e la demo è stata provata end-to-end.

## 11. Verifiche trasversali e stop condition

| Controllo | Quando | Impatto se fallisce |
|---|---|---|
| Versioni compatibili Python/client/ES | M0 | Blocca integrazione |
| Identificativi stabili e dedup coerente | M2 | Blocca pooling e qrels affidabili |
| Cleaning preserva la notizia | M2 | Blocca valutazione di qualità |
| Stesso engine per Web ed evaluation | M3 | Blocca validità delle metriche rispetto alla demo |
| Topic/rubrica definiti prima delle etichette | M5 | Blocca produzione massiva gold/silver |
| Test set segregato dal tuning | M5–M6 | Blocca credibilità della comparazione finale |
| Manifest completi e qrels versionati | M6 | Blocca riproducibilità delle conclusioni |
| Installazione da clone pulito | M7 | Blocca consegna operativa |

## 12. Cosa fare ora: prima iterazione concreta

Per evitare di avviare troppe attività contemporaneamente, l'ordine consigliato dei primi commit è:

1. **Commit 1 — Documentation & skeleton:** `docs/`, README placeholder, `.gitignore`, progetto Python, struttura moduli.
2. **Commit 2 — Local infrastructure:** Compose Elasticsearch con versione fissata, `.env.example`, health check.
3. **Commit 3 — Minimal application:** FastAPI health endpoint, pagina HTML e test automatici.
4. **Commit 4 — Retrieval fixture:** mapping, import di fixture, query BM25, endpoint search e UI risultati.
5. **Commit 5 — Corpus pipeline skeleton:** reader del dump e output normalizzato, predisposizione a M2.

**Gate immediato:** non iniziare la costruzione massiva della ground truth prima di avere ID documentali e testo normalizzato stabili. È invece opportuno predisporre fin da subito il formato dei topic e la rubrica.

## 13. Tracciabilità tra requisito e milestone

| Requisito PRD | Milestone di implementazione | Evidenza finale |
|---|---|---|
| HW-01 / FR-01–03 | M2, M3 | Corpus importato, indice e manifest |
| HW-02 / FR-04, FR-07 | M1, M3 | Web UI funzionante |
| FR-05–06 | M3, M4 | Profili retrieval ed esperimenti |
| HW-03 / FR-08–10 | M5, M6 | Protocollo, qrels, run, metriche e analisi |
| HW-04 / FR-11 | M0, M7 | GitHub, README, setup ripetibile |
| HW-05 | M7 | Presentazione ~20 min senza codice |
| HW-06 | M7 | Demo live validata |

## 14. Criteri per gestire modifiche e scope

- Una scelta che modifica il **corpus** aggiorna versione della pipeline, manifest e potenzialmente tutti gli indici/run/qrels collegati.
- Una scelta che modifica un **analyzer** richiede nuovo indice; una modifica dei **boost** richiede nuova run e profilo versionato.
- Un cambiamento a **topic/rubrica/split** dopo la produzione di giudizi richiede una nuova versione benchmark e un'analisi d'impatto.
- Una nuova feature viene approvata solo se ha ipotesi sperimentale, costo previsto e non ritarda la consegna dei Must.
- Tutte le decisioni non definitive vanno chiuse con un risultato di pilot o un ADR, non tramite cambiamenti silenziosi nel codice.
