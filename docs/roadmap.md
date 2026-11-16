# Roadmap end-to-end — Wikinews Search Engine

**Versione documento:** 0.2.2 · **Data:** 2026-11-16 · **Stato:** piano approvato come sequenza di riferimento

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
- La raccolta del gold procede in parallelo allo sviluppo: blocca le conclusioni sperimentali e la release accademica finale, ma non l'implementazione, i test su fixture o la pubblicazione del sito per i validatori.
- Distinguere sempre gli stati **implementato e verificato su fixture**, **raccolta in corso** e **validato su benchmark reale**. Dati sintetici e risultati provvisori non sono evidenze sperimentali finali.

## 2. Quadro generale delle milestone

| Milestone | Risultato dimostrabile | Dipendenze | Gate di uscita |
|---|---|---|---|
| M0 — Repo e tecnologia | Progetto Python, Compose, lint, test | Nessuna | Completato: avvio ambiente e CI base verificati |
| M1 — Vertical slice | UI → API → Elasticsearch → risultati su fixture | M0 | Completato localmente: ricerca browser e Python su fixture |
| M2 — Corpus pipeline | Dump letto, ripulito, deduplicato e manifestato | M0 | Completato localmente: 11.032 articoli e build riproducibili |
| M3 — Baseline completa | E0/E1 con corpus reale, API/UI stabile | M1, M2 | Completato localmente: 11.032 articoli per indice e run identiche dopo rebuild |
| M4 — Retrieval avanzato | E2/E3/E4 e possibili estensioni | M3 | Completato localmente: E2/E3/E4, highlight e baseline invariate |
| M5-A — Infrastruttura benchmark | Topic, pooling, schema giudizi, pacchetti silver Codex ed export | M3, M4 | Completata localmente su fixture; 48 coppie esterne riconciliate, nessun gold/silver reale |
| M5-B — Strumento di annotazione | Pagina condivisa, assegnazioni e revisione | M5-A | Completata localmente su fixture: flusso multiutente, persistenza, revisione ed export verificati |
| M5-C — Pilot e congelamento | Calibrazione, budget, topic e protocollo congelati | M5-A, M5-B; M7-A per pilot online | 24 silver di calibrazione importate; confronto umano, tempi e congelamento pendenti |
| M5-D — Raccolta e consolidamento | Gold/silver separati e pool tracciabili | M5-C; M7-A per raccolta condivisa | Copertura prevista raggiunta e qualità annotazione controllata |
| M6-A — Implementazione valutazione | Metriche, confronti e generazione report | M5-A | Calcoli verificati su fixture con risultati attesi |
| M6-B — Esperimenti reali | Tuning development, confronto finale, error analysis | M4, M6-A; gold development per tuning, M5-D per finale | Test gold usato una volta secondo protocollo congelato |
| M7-A — Pubblicazione operativa | Sito condivisibile con i validatori | M5-B | Accessi, persistenza, backup e ripristino verificati online |
| M7-B — Consegna accademica | GitHub, README, slide, demo live | M6-B | Installazione pulita e presentazione provate |

**Parallelismo consentito:** dopo M1, la preparazione dei topic e delle linee guida può avanzare insieme al preprocessing. Il pooling definitivo, invece, dipende dalle run candidate disponibili e dall'identità stabile dei documenti.

**Percorso operativo dopo M4:** M5-A → M5-B → M7-A → M5-C → M5-D. Il pilot può essere provato localmente prima della pubblicazione. M6-A e la preparazione di documentazione, slide e demo possono avanzare mentre si costruisce lo strumento o si raccolgono i giudizi. Il tuning M6-B può iniziare su development gold consolidato; la valutazione finale aspetta M5-D e il congelamento del profilo. La numerazione M7 non implica che la pubblicazione operativa debba aspettare M6.

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

- [x] Implementare `E2`: boosting del titolo rispetto al corpo; parametro configurabile.
- [x] Implementare `E3`: fuzzy matching controllato; scegliere se basso boost, fallback o entrambe le varianti testate.
- [x] Implementare `E4`: phrase search; chiarire semantica delle virgolette e comportamento UI.
- [x] Valutare `E5`: sinonimi controllati rinviati, con motivazione in ADR 0005.
- [x] Valutare miglioramenti UI: highlight e filtro per intervallo date **solo** quando affidabile.
- [x] Scrivere test unitari del query builder e test integrazione con coppie query-documento difficili.
- [x] Evitare la combinazione indiscriminata di feature: E3/E4/E5 devono confrontarsi singolarmente con E2.

### Exit criteria

Ogni profilo produce risultati e run con ID/versione riconoscibili. Le feature non interrompono la UI baseline; eventuali regressioni sono misurabili e documentate. La selezione del profilo finale **non** usa il test gold.

**Stato: M4 completata e verificata localmente (2026-11-16).**
E2/E3/E4 e highlight disponibili in API/UI/Python, con run ripetibili anche dopo
rebuild. E0/E1 conservano gli hash M3. Nessun cambiamento al corpus; sinonimi e
filtro date rinviati. Evidenze nel [report M4](m4-validation.md), semantica e
limiti in [ADR 0005](decisions/0005-advanced-retrieval.md). CI remota da verificare
dopo il push; selezione del profilo finale riservata a M5/M6.

## 8. Fase M5 — Benchmark e ground truth multi-sorgente

**Obiettivo:** implementare il benchmark e lo strumento collaborativo prima della raccolta massiva, poi produrre giudizi tracciabili mentre il progetto continua ad avanzare.

**Budget umano:** tre validatori, ciascuno con 4–6 ore disponibili: **12–18 ore complessive**, incluse calibrazione, annotazione e risoluzione dei disaccordi. Nessuna scadenza introdotta. I target ~600 gold e ~1.200 silver saranno rivalutati sui tempi del pilot; il numero di coppie distinte va separato dal numero di annotazioni, che include le doppie letture.

**Riferimento esplorativo:** il lavoro in `C:\Users\lucap\Downloads\itwikinews-NS0-20250320-ENTERPRISE-HTML.json\evaluation\pilot` contiene quattro topic, 48 coppie e proposte dell'assistente, con zero revisioni umane dichiarate. Riutilizzare bisogni informativi, rubriche e casi limite come conoscenza da verificare. La selezione esterna conta 11.031 documenti contro gli 11.032 del progetto: riconciliare ID, revisioni e testi con M2, senza importare automaticamente policy, pool o etichette. Le proposte non costituiscono gold né silver controllato; i casi usati per calibrazione non entrano nel test finale. Il percorso locale è un riferimento di provenienza, non una dipendenza di installazione.

### M5-A — Infrastruttura benchmark

#### Topic e rubriche

- [x] Formalizzare formato topic: query, information need, inclusioni/esclusioni, tipologia, tema, periodo, famiglia evento.
- [x] Implementare validazione della rubrica `0/1/2`, astensioni e split per famiglie, evitando eventi quasi duplicati tra development e test.
- [x] Predisporre varianti con refusi come proprietà del topic originale, non topic indipendenti; compilazione reale in M5-C.

#### Candidate generation e pooling

- [x] Predisporre esecuzione delle run E0–E4 con top-k documentato e salvataggio TREC; verificare il flusso su fixture prima delle run definitive.
- [x] Realizzare adapter per ricerca Wikinotizie e salvare ranking con timestamp e parametri; verifica HTTP simulata, live rinviato.
- [x] Mappare risultati esterni al `document_id` del dump; registrare quelli assenti dallo snapshot.
- [x] Unire e deduplicare i candidati per topic, preservando provenienza/rank delle run.
- [x] Implementare selezione separata dal pool, quote per run e seed registrati; budget reale da fissare in M5-C prima dei giudizi.
- [x] Registrare numero di candidati, copertura per run e casi non mappati.

#### Giudizi, silver ed export

- [x] Implementare schema unificato per giudizi, motivazioni, evidenza, metadati dell'annotatore e versioni di topic, rubrica e testo.
- [x] Preparare silver tramite **nuova chat Codex in VS Code**: workspace autonomo, prompt/schema versionati, validatore Python standalone, import degli output originali e corretti; nessun client API LLM.
- [x] Predisporre lo stesso pacchetto di criteri e testo pulito per umani e LLM, senza rank o etichette precedenti.
- [x] Implementare export gold/silver separati, checksum e manifest; astensioni e coppie non giudicate non diventano grado `0`.
- [x] Testare deduplicazione del pool, split per famiglia, citazioni, astensioni, separazione delle fonti ed export su fixture.

**Gate M5-A:** contratti e pipeline funzionano su fixture senza gold reale. La prima esecuzione silver reale è successivamente documentata nel [diario M5-C](m5c-validation.md); il benchmark definitivo resta pendente.

**Stato: M5-A completata e verificata localmente (2026-11-16).** Quattro topic adattati come bozze di calibrazione; 48/48 coppie presenti con revisione corrispondente, ma testo pulito diverso in tutti i casi. Nessuna etichetta importata. Workflow e limiti in [evaluation.md](evaluation.md); evidenze in [m5a-validation.md](m5a-validation.md). UI successivamente completata in M5-B; raccolta reale ancora da eseguire.

### M5-B — Strumento condiviso di annotazione

- [x] Integrare nell'app una pagina con query, bisogno informativo, inclusioni/esclusioni e rubrica del topic sempre visibili accanto a titolo e testo completo congelato.
- [x] Aggiungere ricerca nel testo ed evidenziazione lessicale facoltativa, senza suggerimenti automatici del grado.
- [x] Offrire scorciatoie `0/1/2`, astensione e “riprendi dopo” come stati distinti; causali rapide e nota libera per motivare il giudizio.
- [x] Acquisire citazioni selezionando passaggi del testo, con riferimenti verificabili alla versione annotata.
- [x] Implementare salvataggio confermato, ripresa della sessione, modifica dell'ultimo giudizio e cronologia delle revisioni; non avanzare silenziosamente se il salvataggio fallisce.
- [x] Assegnare blocchi per topic, con ordine dei documenti indipendente dal ranking e sovrapposizioni programmate per la doppia annotazione.
- [x] Escludere origine, rank, silver e giudizi altrui dai dati restituiti all'annotatore durante la valutazione indipendente, non soltanto dalla visualizzazione.
- [x] Predisporre ruoli di annotatore e coordinatore, coda dei dubbi e adjudication da parte del terzo revisore; conservare entrambe le valutazioni iniziali e la decisione finale separatamente.
- [x] Esporre interfacce per assegnazioni, salvataggio/versionamento dei giudizi, adjudication ed export, con autorizzazioni e gestione dei salvataggi concorrenti.
- [x] Mostrare avanzamento personale e complessivo, astensioni e revisioni pendenti; mantenere giudizi e risultati test fuori dagli strumenti di tuning. L'accesso per annotare il test non autorizza il suo uso sperimentale anticipato.
- [x] Rendere la raccolta indipendente da chiamate live a Elasticsearch, Web o LLM, leggendo topic e documenti dai pacchetti congelati.
- [x] Verificare il flusso multiutente: isolamento dei giudizi, autorizzazioni, salvataggi simultanei, interruzione/ripresa, modifica e adjudication.

**Gate M5-B:** il percorso completo funziona localmente con più utenti e dati persistenti. È possibile procedere alla pubblicazione M7-A senza attendere annotazioni reali.

**Stato: M5-B completata e verificata localmente (2026-11-16).** UI dedicata desktop/mobile,
account locali, SQLite persistente, blocchi congelati, finalizzazione automatica,
revisione indipendente ed export per split. 173 test superati, incluse tre sessioni
browser e regressioni retrieval; backup/ripristino locale verificato. Nessun giudizio
reale raccolto. Guida in [annotation.md](annotation.md), evidenze in
[m5b-validation.md](m5b-validation.md) e decisioni in
[ADR 0006](decisions/0006-collaborative-annotation.md). CI remota da verificare dopo il push.

### M5-C — Pilot, budget e congelamento

- [x] Prima prova silver indipendente su 24 coppie di calibrazione: GPT-6.0-Astra
  dichiarato, validazione/import/export completati il 16 novembre 2026; 13 gradi 2,
  2 gradi 1, 9 gradi 0, nessuna astensione. [Diario](m5c-validation.md).
  Questo risultato non completa la raccolta di produzione M5-D.

- [x] Costruire **pilot di 4 topic**, uno per tipologia, usando strategia ibrida corpus/user-driven e riconciliando gli spunti esterni con il corpus M2.
- [ ] Far giudicare indipendentemente un piccolo insieme comune ai tre validatori, poi discutere i disaccordi e correggere la rubrica prima della produzione.
- [ ] Misurare tempi di lettura, annotazione e revisione; dimensionare coppie distinte e quota doppia nel budget di 12–18 ore, riservando tempo per calibrazione e adjudication.
- [ ] Portare il benchmark al target di **40 topic**: 10 evento, 10 tema, 10 entità, 10 multi-vincolo. Stratificare temi e periodi; non copiare automaticamente query dai titoli.
- [ ] Congelare split **24 development / 16 test** per famiglie, escludendo dal test i casi di calibrazione; documentare eventuali variazioni motivate dal pilot.
- [ ] Fissare top-k, budget, quote di campionamento, copertura gold e doppia annotazione prima di osservare i giudizi di produzione; preservare gold su parte development e **tutti i topic di test**.
- [ ] Eseguire e conservare run E0–E4 e ricerca Wikinotizie per i topic definitivi; congelare pool, testi, assegnazioni e manifest prima della raccolta.
- [ ] Scegliere il modello nella chat Codex e congelare prompt e pacchetti sulla sola calibrazione/development prima del silver di produzione; registrare modello dichiarato o `unknown`, senza inventare un identificatore.

**Gate M5-C:** ambiguità affrontate, tempi misurati, budget motivato e protocollo congelato. Una modifica successiva richiede nuova versione e analisi d'impatto sui giudizi già raccolti.

**Stato: preparazione locale implementata e verificata (2026-11-16), gate non ancora
superato.** Pacchetto reale di 24 coppie pronto per 72 annotazioni indipendenti;
40 topic di produzione in bozza, run E0–E4 del pilot e pool di 151 coppie conservati.
Timer, discussione tripla, report, budget e congelamento verificati su fixture.
Nessun giudizio umano reale e nessun protocollo di produzione congelato. Procedura
in [m5c-pilot.md](m5c-pilot.md), evidenze in [m5c-validation.md](m5c-validation.md),
decisioni in [ADR 0007](decisions/0007-pilot-calibration.md).

### M5-D — Raccolta e consolidamento in parallelo

- [ ] Annotare manualmente gold secondo assegnazioni e campionamento congelati, mentre proseguono M6-A e la preparazione della consegna.
- [ ] Eseguire il silver in una nuova chat Codex e workspace dedicato ai pacchetti selezionati, senza fornire gold, rank o giudizi altrui; validare e importare gli output con metadati. Separazione organizzativa, non sandbox tecnica; riproducibili gli artefatti, non garantite identiche etichette fra chat.
- [ ] Controllare qualità con doppie annotazioni programmate e revisione dei disaccordi da parte del terzo validatore; documentare accordo umano e casi irrisolti.
- [ ] Gestire esplicitamente `unjudged`, rinvii e astensioni: nessuna conversione automatica in non rilevanza e nessuna media tra gold, silver e ranking esterno.
- [ ] Versionare separatamente gold e silver, con checksum e protocolli del benchmark.
- [ ] Verificare copertura prevista, evidenze, integrità degli export e disponibilità delle stesse coppie per il confronto gold/silver.

### Exit criteria M5 complessiva

Esistono topic, split, candidate pools, qrels gold e silver separati, ranking Wikinotizie come **run esterna** e manifest di provenienza. Il benchmark è utilizzabile da script senza consultazione live del Web/LLM. Non è necessario rispettare numeri arbitrari se il pilot giustifica un diverso budget; la scelta va documentata.

## 9. Fase M6 — Valutazione, selezione e analisi degli errori

**Obiettivo:** dimostrare sperimentalmente quali configurazioni funzionano meglio e quanto è affidabile il giudice automatico.

### M6-A — Implementazione valutazione senza attendere il gold

- [ ] Implementare report `ir-measures`: nDCG@10, P@5 (soglia di rilevanza dichiarata), eventuale MRR@10.
- [ ] Implementare copertura in top-k, analisi degli unjudged, confronto gold/silver sulle stesse coppie e generazione di tabelle/grafici con manifest.
- [ ] Verificare calcoli e report con fixture sintetiche dai risultati attesi, inclusi giudizi mancanti e astensioni; distinguere chiaramente questi output dagli esperimenti reali.

**Gate M6-A:** pipeline di valutazione pronta e verificata, anche con raccolta gold ancora in corso.

### M6-B — Esperimenti reali e valutazione finale

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

## 10. Fase M7 — Pubblicazione operativa e consegna accademica

**Obiettivo:** soddisfare integralmente la consegna del professore con un repository leggibile e una dimostrazione affidabile.

### M7-A — Pubblicazione operativa per i validatori

Questa fase dipende da M5-B, non dagli esperimenti finali. Il sito può essere condiviso per il pilot e per raccogliere le validazioni mentre il resto del progetto prosegue.

- [ ] Scegliere e documentare provider, costi e configurazione del deployment prima della pubblicazione; la revisione della roadmap non implica una scelta di hosting o un acquisto.
- [ ] Pubblicare il sito con HTTPS e accessi individuali per i tre validatori, verificando i permessi di annotatore e coordinatore.
- [ ] Configurare archivio persistente per assegnazioni e giudizi, segreti tramite configurazione e backup; mantenere Elasticsearch non esposto pubblicamente.
- [ ] Verificare accesso da computer distinti, salvataggi concorrenti e ripresa delle sessioni; l'annotazione deve funzionare anche quando i servizi di ricerca o LLM non sono disponibili.
- [ ] Eseguire una prova di backup e ripristino e verificare che aggiornamento o riavvio dell'app non cancellino giudizi e cronologia.
- [ ] Documentare avvio, monitoraggio degli errori di salvataggio, recupero dei dati e procedura di aggiornamento, preservando i pacchetti congelati delle sessioni in corso.
- [ ] Condividere istruzioni per accesso, rubrica, scorciatoie, astensioni e segnalazione dei problemi; verificare il percorso prima di iniziare la raccolta reale.

**Gate M7-A:** sito raggiungibile dai colleghi, autorizzazioni corrette, persistenza e ripristino verificati. La pubblicazione operativa non certifica il completamento del benchmark o della consegna accademica.

### M7-B — Consegna accademica

Documentazione, struttura delle slide e preparazione della demo possono avanzare durante M5-D. Risultati, conclusioni e release finale richiedono M6-B completata.

#### Release repository

- [ ] Aggiornare `README.md`: panoramica, requisiti hardware/software, setup, download dump, `.env`, `make up`, ingest, run, test, benchmark, troubleshooting.
- [ ] Documentare architettura reale e decisioni finali; rimuovere voci obsolete dal blueprint.
- [ ] Aggiornare `docs/dataset.md`, `docs/evaluation.md` e ADR effettivamente necessari.
- [ ] Inserire link alla fonte e indicazioni corrette su copyright/licenza dei contenuti; non committare l'intero dump.
- [ ] Verificare che non siano presenti segreti, file temporanei, indici Elasticsearch o gigabyte di raw data.
- [ ] Pubblicare release/tag e commit di riferimento dei risultati sperimentali.
- [ ] Provare installazione da clone pulito con i soli prerequisiti dichiarati.

#### Presentazione di circa 20 minuti

Struttura orientativa, da adattare ai risultati disponibili:

| Segmento | Durata indicativa | Contenuto |
|---|---:|---|
| Problema e vincoli | 2 min | Homework, corpus, obiettivi |
| Sfide dati/architettura | 4 min | Parsing, pulizia, index design, stack |
| Retrieval e scelte | 4 min | BM25, analyzer, boosting, fuzzy/phrase |
| Ground truth e metodologia | 5 min | Pooling, gold/silver, baseline esterna, metriche |
| Risultati e limiti | 5 min | Tabelle/grafici, trade-off, errori |

Totale ~20 minuti; **nessun codice nelle slide**, come richiesto. La demo live è un deliverable separato e va collocata nei tempi richiesti dal docente, non forzatamente dentro questi 20 minuti.

#### Demo live e contingency

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
| Topic/rubrica, pool e quote congelati prima dei giudizi di produzione | M5-C | Blocca produzione massiva gold/silver, non sviluppo su fixture |
| Isolamento dei giudizi e salvataggi multiutente affidabili | M5-B, M7-A | Blocca raccolta condivisa |
| Accessi, persistenza, backup e ripristino verificati | M7-A | Blocca apertura del sito ai validatori |
| Test set segregato dal tuning | M5–M6 | Blocca credibilità della comparazione finale |
| Gold in raccolta o copertura non ancora raggiunta | M5-D | Blocca esperimenti finali M6-B, non M6-A o pubblicazione M7-A |
| Manifest completi e qrels versionati; profilo e analisi congelati | M6-B | Blocca valutazione finale e riproducibilità delle conclusioni |
| Installazione da clone pulito | M7-B | Blocca consegna accademica |

## 12. Cosa fare ora: prima iterazione concreta

M0–M4, M5-A e M5-B sono completate localmente. Il percorso di riferimento è:

1. **M5-A — Completata:** topic/rubriche, pooling, giudizi, pacchetti silver Codex ed export verificati su fixture; materiale esplorativo riconciliato.
2. **M5-B — Completata:** pagina dedicata, assegnazioni, salvataggi persistenti, giudizi indipendenti, adjudication ed export; collaudo multiutente locale superato su fixture.
3. **M7-A — Sito condiviso:** decisione di hosting e pubblicazione, accessi e prova di ripristino prima della raccolta reale.
4. **M5-C — Pilot:** calibrazione dei tre validatori, misura dei tempi, dimensionamento e congelamento del protocollo e dei pool.
5. **M5-D e M6-A — Lavoro parallelo:** raccolta gold/silver e implementazione/verifica dei report; preparazione di documentazione e demo. M6-A può iniziare già dopo M5-A.
6. **M6-B e M7-B — Chiusura scientifica:** tuning sul development disponibile, congelamento del profilo, valutazione finale dopo consolidamento e consegna accademica.

**Gate immediato:** M7-A, scegliere hosting e pubblicare il flusso verificato localmente, con accessi e ripristino online. La raccolta massiva parte soltanto dopo il pilot e il congelamento; nessun dato sintetico sostituisce il benchmark reale.

## 13. Tracciabilità tra requisito e milestone

| Requisito PRD | Milestone di implementazione | Evidenza finale |
|---|---|---|
| HW-01 / FR-01–03 | M2, M3 | Corpus importato, indice e manifest |
| HW-02 / FR-04, FR-07 | M1, M3 | Web UI funzionante |
| FR-05–06 | M3, M4 | Profili retrieval ed esperimenti |
| HW-03 / FR-08–10 | M5-A/C/D, M6-A/B | Protocollo, qrels, run, metriche e analisi |
| Supporto alla validazione FR-08–10 | M5-B, M7-A | Strumento condiviso, giudizi indipendenti, cronologia ed export |
| HW-04 / FR-11 | M0, M7-A/B | GitHub, README, setup e deployment ripetibili |
| HW-05 | M7-B | Presentazione ~20 min senza codice |
| HW-06 | M7-B | Demo live validata |

## 14. Criteri per gestire modifiche e scope

- Una scelta che modifica il **corpus** aggiorna versione della pipeline, manifest e potenzialmente tutti gli indici/run/qrels collegati.
- Una scelta che modifica un **analyzer** richiede nuovo indice; una modifica dei **boost** richiede nuova run e profilo versionato.
- Un cambiamento a **topic/rubrica/split** dopo la produzione di giudizi richiede una nuova versione benchmark e un'analisi d'impatto.
- Una nuova feature viene approvata solo se ha ipotesi sperimentale, costo previsto e non ritarda la consegna dei Must.
- Tutte le decisioni non definitive vanno chiuse con un risultato di pilot o un ADR, non tramite cambiamenti silenziosi nel codice.
- Gli aggiornamenti del software durante la raccolta devono preservare giudizi e pacchetti congelati; cambiamenti di corpus, topic o rubrica richiedono versionamento e revisione esplicita delle annotazioni interessate.
