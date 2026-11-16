# Product Requirements Document (PRD)

**Progetto:** Wikinews Search Engine — Homework 4, Ingegneria dei Dati  
**Versione documento:** 0.1.0 — progettazione preliminare  
**Data:** 2026-11-16  
**Stato:** scelte tecnologiche e impostazione metodologica approvate; dettagli subordinati alla validazione sul corpus  
**Documenti correlati:** [Architettura](./architeture.md) · [Roadmap](./roadmap.md)

## 1. Sintesi

Realizzare un motore di ricerca **full-text per le notizie in italiano di Wikinotizie**, basato su Elasticsearch e consultabile tramite interfaccia Web. Il sistema deve essere installabile e dimostrabile localmente, con codice e istruzioni pubblicati su GitHub.

L'elemento distintivo non sarà il numero di funzionalità dell'interfaccia, ma la capacità di **motivare e misurare le scelte di Information Retrieval**: baseline BM25, analisi linguistica per l'italiano, pesatura dei campi, ricerca fuzzy, ricerca per frase ed eventuali sinonimi controllati. La valutazione utilizzerà un benchmark riproducibile con pooling, giudizi LLM (*silver*), annotazioni umane (*gold*) e ranking di Wikinotizie come baseline esterna, **non** come verità di rilevanza.

## 2. Vincoli espliciti dell'Homework 4

La consegna del docente richiede:

| ID | Requisito vincolante | Evidenza di completamento |
|---|---|---|
| HW-01 | Sistema di search delle notizie italiane del dump assegnato | Corpus indicizzato e ricerca operativa |
| HW-02 | Interfaccia Web per interrogare le notizie | Ricerca eseguibile da browser |
| HW-03 | Definire **e implementare** una strategia di test | Protocollo, query, giudizi, run e metriche riproducibili |
| HW-04 | Pubblicare il codice su GitHub con istruzioni di installazione e utilizzo | Repository accessibile e README completo |
| HW-05 | Presentazione di circa **20 minuti** | Sfide tecnico-metodologiche, soluzioni, strategia di test e risultati sperimentali; **senza codice nelle slide** |
| HW-06 | Demo live del sistema | Ricerca funzionante nell'ambiente predisposto |

**Corpus vincolato:** snapshot del 20 marzo 2025, file `itwikinews-NS0-20250320-ENTERPRISE-HTML.json.tar.gz`:

<https://dumps.wikimedia.org/other/enterprise_html/runs/20250320/itwikinews-NS0-20250320-ENTERPRISE-HTML.json.tar.gz>

L'utilizzo di Elasticsearch, il framework applicativo, la ground truth multi-sorgente e gli altri dettagli sotto sono **scelte progettuali**, non requisiti aggiuntivi del professore.

## 3. Problema, visione e principi

**Problema.** Mettere a disposizione una ricerca che recuperi e ordini articoli pertinenti a un bisogno informativo, anche quando la formulazione della query differisce dal testo delle notizie, e dimostrarne sperimentalmente l'efficacia.

**Visione.** Un motore lessicale avanzato, sufficientemente semplice da installare e utilizzare, ma dotato di una procedura di valutazione trasparente e riproducibile.

**Principi di progetto:**

1. **Retrieval prima delle feature:** la rilevanza dei risultati ha precedenza sul numero di funzionalità.
2. **Confronti controllati:** modificare una scelta alla volta quando possibile; misurare gli effetti rispetto a una baseline.
3. **Separazione delle fonti di giudizio:** gold umano, silver LLM e ranking esterno non sono intercambiabili.
4. **Provenienza dei dati:** ogni documento indicizzato deve poter essere ricondotto al dump, alla revisione e al preprocessing.
5. **Riproducibilità:** configurazioni, dipendenze, indici, run, protocollo e versioni devono essere tracciabili.
6. **Demo affidabile:** il sistema di ricerca non deve dipendere da servizi LLM o Wikinotizie disponibili in tempo reale.

## 4. Perimetro e utenti

### 4.1 Utenti di riferimento

- **Utente della ricerca:** inserisce parole chiave in italiano, legge i risultati e apre le notizie.
- **Sviluppatore/ricercatore:** importa il corpus, definisce configurazioni di ricerca, genera run e misura metriche.
- **Valutatore umano:** assegna giudizi di rilevanza a coppie query-documento usando una rubrica condivisa.
- **Docente/dimostratore:** esegue installazione o demo, comprende motivazioni e risultati dei test.

### 4.2 Inclusioni

- Ricerca full-text su **titolo e corpo** dell'articolo, con classifica BM25.
- Analyzer italiano e confronto con analyzer standard.
- Boosting dei campi, fuzzy matching e ricerca per frase.
- Visualizzazione di titolo, estratto, URL, eventuale data e categoria.
- Filtro per intervallo temporale **solo quando il dato temporale è validato**; evidenziazione dei termini come miglioria dell'interfaccia.
- Pipeline offline per ingestione e pulizia, configurazioni di indicizzazione, esperimenti e valutazione.
- Benchmark con gold manuale, silver LLM, baseline esterna Wikinotizie e metriche IR.

### 4.3 Esclusioni iniziali

- RAG, chatbot, question answering e retrieval semantico/vettoriale.
- Crawling continuo, aggiornamento live del corpus e sincronizzazione con Wikinotizie.
- Account utente, autenticazione applicativa e profili personali.
- Database relazionale aggiuntivo, infrastruttura cloud o microservizi.
- Autocomplete e sinonimi controllati come prerequisiti della consegna: **eventuali estensioni** da introdurre solo se motivate.

Il sistema è **ricerca di documenti**, non generazione di risposte.

## 5. Corpus e criteri di ammissibilità

### 5.1 Dati osservati nell'audit iniziale

I conteggi riportati nell'audit condiviso sono **osservazioni preliminari**, non dimensioni già definitive del corpus indicizzato:

| Indicatore | Valore osservato |
|---|---:|
| Record totali | 12.261 |
| Identificativi di pagina distinti | 12.213 |
| Record con categoria `Pubblicati` | 11.066 |
| Pagine distinte comparsa almeno una volta in `Pubblicati` | 11.032 |
| `article_body.html` / `article_body.wikitext` | Presenti nei record esaminati |
| `date_created` | 242 record |

L'audit segnala anche revisioni multiple, testo non giornalistico (*boilerplate*) e date recuperabili da template con ambiguità residue. La prima fase dati dovrà validare campioni reali e fissare il conteggio finale.

### 5.2 Unità documentale

**Un documento ricercabile = un articolo giornalistico di Wikinotizie**. Nessun chunking iniziale per paragrafi. Il `identifier` è la chiave stabile della pagina; `version.identifier` identifica la revisione selezionata.

### 5.3 Regole preliminari

- Considerare la categoria `Pubblicati` come **criterio candidato** d'inclusione; verificarne precisione e copertura prima di renderlo definitivo.
- Gestire revisioni multiple per pagina con una politica documentata e deterministica, senza perdere tracciabilità.
- Pulire HTML preservando la prosa dell'articolo, non menu, navigazione, template o boilerplate.
- Conservare `url`, titolo, categorie e metadati di provenienza; non usare automaticamente tutte le categorie per il ranking.
- Trattare `publication_date` come opzionale con provenienza e stato di validazione.
- Non equiparare automaticamente `date_created`, `date_modified` ed `event.date_published` alla data giornalistica della notizia.
- Scartare o mettere in quarantena i record non idonei secondo regole esplicite e produrre statistiche degli scarti.

### 5.4 Modello logico indicizzato

| Campo | Scopo |
|---|---|
| `document_id` | ID stabile di pagina (`identifier`) |
| `revision_id` | Revisione indicizzata |
| `title` | Ricerca full-text, visualizzazione |
| `body` | Ricerca full-text sul testo pulito |
| `abstract` | Metadato/estratto, se affidabile; non sostituisce `body` |
| `url` | Apertura della fonte originale |
| `categories` | Metadati/filtro potenziale, se verificati |
| `publication_date` | Filtro facoltativo su date validate |
| `publication_date_status` | Stato/provenienza della data |
| `source_snapshot` / `processing_version` | Provenienza e riproducibilità |

## 6. Requisiti funzionali

| ID | Priorità | Requisito | Criterio di accettazione |
|---|---|---|---|
| FR-01 | Must | Importare lo snapshot indicato | Comando documentato; riepilogo di record letti, validi, esclusi, duplicati e falliti |
| FR-02 | Must | Preprocessing e tracciabilità | Test su fixture; output deterministico con identificativi, revisione e versione pipeline |
| FR-03 | Must | Indicizzazione full-text | Titolo/corpo indicizzati; conteggio confrontabile con manifest dati |
| FR-04 | Must | Ricerca da Web UI | Query inserita da browser, risposta ordinata con link alle notizie |
| FR-05 | Must | BM25 e analyzer alternativi | Baseline standard e configurazione italiana eseguibili sullo stesso corpus logico |
| FR-06 | Must | Profili avanzati | Title boosting, fuzzy e phrase search eseguibili e testabili come profili distinti |
| FR-07 | Must | Risultati navigabili | Titolo, estratto, URL e paginazione/limite risultati; gestione di zero risultati |
| FR-08 | Must | Dataset di valutazione | Topic, pool e annotazioni mantenuti in formati strutturati e versionati |
| FR-09 | Must | Metriche e confronti | Generazione run per profilo e calcolo nDCG@10 e P@5 su qrels dichiarati |
| FR-10 | Must | Valutazione multi-sorgente | Gold umano e silver LLM separati; ranking Wikinotizie registrato come run esterna |
| FR-11 | Must | GitHub e manuale d'uso | Prerequisiti, setup, import, avvio, test, valutazione e demo documentati |
| FR-12 | Should | Evidenziazione termini | Highlight visibile con fallback sicuro |
| FR-13 | Should | Filtro per data | Disponibile solo per documenti con data valida; comportamento dei mancanti esplicitato |
| FR-14 | Could | Sinonimi controllati | Esperimento isolato; applicazione non indiscriminata |
| FR-15 | Could | Autocomplete | Solo se non compromette il tempo dedicato alla valutazione |

**Priorità:** *Must* è richiesto per la definizione di completamento del progetto concordato; non coincide necessariamente con un vincolo esplicito del docente. *Should/Could* sono differibili.

## 7. Strategia sperimentale e ground truth

### 7.1 Benchmark di topic

**Target iniziale:** 40 topic con query breve, bisogno informativo, criteri d'inclusione/esclusione e metadati. Quattro famiglie da 10: evento specifico, tema, entità, vincoli multipli; copertura stratificata anche per ambito tematico e periodo.

**Split previsto:** 24 topic *development* e 16 topic *test*, senza sovrapposizioni di eventi o famiglie di query quasi identiche. Le query perturbate da refusi restano varianti della stessa famiglia, non nuovi topic indipendenti.

**Pilot iniziale:** 4 topic (uno per famiglia) per validare rubrica e workflow, **prima** di espandere l'annotazione. La costruzione dei topic avverrà con approccio ibrido corpus-driven e user-driven, evitando di copiare i titoli dei risultati.

### 7.2 Rubrica di giudizio

| Label | Significato operativo |
|---|---|
| `2` | Il documento soddisfa direttamente il bisogno informativo e i suoi vincoli essenziali |
| `1` | Fornisce informazioni utili ma parziali, secondarie o meno specifiche |
| `0` | Non soddisfa il bisogno; sole coincidenze lessicali non bastano |
| `unjudged` / `abstain` | **Non è una label di rilevanza**; richiede trattamento o revisione esplicita |

Il giudizio valuta **rilevanza rispetto all'intento**, non veridicità fattuale. Per le query temporali la narrativa distingue data dell'evento e data di pubblicazione.

### 7.3 Le tre fonti, con ruoli differenti

1. **Ranking Wikinotizie:** baseline esterna e sorgente di pooling, ottenuta dalla ricerca online. Riconciliare gli ID con lo snapshot; il sito attuale e il dump non sono identici. La posizione non è una label 0–2.
2. **LLM-as-a-Judge (es. GPT Astra):** etichette *silver* da query, intent e testo pulito; output strutturato, motivazione/evidenza, possibilità di astensione. Registrare modello, versione, prompt e parametri. Non dipendere dall'LLM nel percorso Web.
3. **Valutazione manuale:** *gold standard* su un sottoinsieme rappresentativo. Il test gold resta riservato alla valutazione finale, non al tuning del motore o del prompt LLM.

Le medesime coppie query-documento devono essere giudicate da gold e silver quando si misura il loro accordo. **Niente voto di maggioranza o media automatica tra le tre fonti.**

### 7.4 Pooling

Generare candidati dai top risultati di più run (BM25 standard, italiano, boosting, fuzzy, phrase) e dalla ricerca Wikinotizie. Deduplicare per `document_id`, registrare provenienza/posizioni, applicare selezione controllata prima di osservare i giudizi; evitare che un solo sistema monopolizzi il pool. Target orientativo silver: circa 20–30 candidati distinti per query, da rivedere in base ai risultati reali.

### 7.5 Metriche e policy

- **Primarie:** nDCG@10 (rilevanza graduata) e Precision@5 (con soglia documentata, proposta `label >= 1`).
- **Aggiuntive:** MRR@10 per topic di evento specifico; error analysis e risultati per query.
- **Qualità dei giudizi:** matrice di confusione, macro-F1 e weighted Cohen's kappa su coppie gold/silver condivise; analisi dei disaccordi.
- **Confronti:** stessi topic, stesso corpus, stessa profondità di ranking, stesso insieme di giudizi quando si comparano configurazioni.
- **Limite:** pooling incompleto; non equiparare *unjudged* a `0`, non proclamare recall assoluto sul corpus senza giudizi esaustivi. Documentare come le metriche gestiscono i documenti non giudicati.
- **Protezione del test:** tuning su development; scelta finale di configurazione e protocollo prima della valutazione test; rendicontare eventuali deroghe.

**Dimensionamenti di lavoro (non quote obbligatorie):** ~600 giudizi manuali, ~1.200 silver; gold su tutte le 16 query di test e 6–8 query di development. Numeri da rivalutare dopo il pilot e le dimensioni dei pool.

### 7.6 Piano di esperimenti

| Run | Variante | Ipotesi testata |
|---|---|---|
| E0 | Analyzer standard + BM25 | Baseline lessicale |
| E1 | Analyzer italiano + BM25 | Vantaggio del preprocessing linguistico |
| E2 | E1 + boosting titolo | Vantaggio della pesatura dei campi |
| E3 | E2 + fuzzy matching | Robustezza agli errori tipografici |
| E4 | E2 + phrase search | Valore della corrispondenza di frase |
| E5 | E2 + sinonimi controllati, se realizzati | Valore/rumore dell'espansione lessicale |

E3, E4 ed E5 sono confrontati individualmente con E2; una combinazione è possibile **solo dopo** le ablation. Il fuzzy non verrà attivato indiscriminatamente; valutare peso ridotto o fallback su pochi risultati.

## 8. Requisiti non funzionali

| ID | Requisito | Verifica |
|---|---|---|
| NFR-01 | Riproducibilità dell'ambiente | Versioni fissate, lockfile, Docker Compose, comandi documentati |
| NFR-02 | Provenienza e determinismo dei dati | Manifest con checksum dump, versioni pipeline e conteggi |
| NFR-03 | Disponibilità della demo locale | Avvio e ricerca end-to-end senza dipendenze da API esterne |
| NFR-04 | Separazione dei segreti | `.env` ignorato da Git; `.env.example` privo di credenziali |
| NFR-05 | Testabilità | Unit test dei trasformatori e query builder, integration test con fixture |
| NFR-06 | Osservabilità minima | Health check, messaggi di errore, log ingestion e tempi di ricerca |
| NFR-07 | Esperimenti riproducibili | Parametri, commit, manifest, run e metriche versionati |
| NFR-08 | Semplicità operativa | Setup documentato eseguibile da una macchina pulita con Docker e Python |

Non fissiamo ora un SLO numerico di latenza o disponibilità: prima misureremo l'hardware di demo e una baseline. Lo stato di completamento richiederà tempi compatibili con un'interazione live, supportati da misure riportate.

## 9. Consegne finali e definizione di «Done»

Il progetto si considera concluso quando:

- Il repository GitHub contiene codice, configurazioni, test e documentazione aggiornata.
- Una persona può installare dipendenze, avviare Elasticsearch, caricare il corpus e usare la ricerca seguendo il README.
- La UI recupera articoli dello snapshot e ne mostra un ranking navigabile.
- Le configurazioni E0/E1/E2 e gli esperimenti avanzati scelti sono riproducibili.
- Esistono topic, policy di pooling, gold/silver separati, run, metriche e analisi critica dei limiti.
- Le conclusioni sperimentali derivano dal test gold non usato per il tuning.
- La presentazione di circa 20 minuti illustra sfide, decisioni, strategia e risultati senza esporre codice nelle slide.
- La demo live e un piano di ripristino funzionano sulla macchina predisposta.

## 10. Rischi e mitigazioni

| Rischio | Impatto | Mitigazione |
|---|---|---|
| HTML sporco/boilerplate | Ranking e giudizi distorti | Pulizia a regole, test su campioni, confronto raw/clean |
| Filtri `Pubblicati` troppo restrittivi | Perdita di notizie | Revisione degli esclusi e policy tracciabile |
| Date ambigue o mancanti | Filtri e topic temporali errati | Campo opzionale, status/provenienza, validazione manuale |
| Drift del motore Wikinotizie online | Baseline non perfettamente comparabile | Snapshot dei risultati esterni, matching a ID locali, limiti espliciti |
| Bias/instabilità del giudice LLM | Silver non affidabile | Rubrica, giudizi ciechi, confronto con gold e versionamento prompt |
| Pool incompleto | Metriche sensibili ai non giudicati | Pooling multi-run, coverage, documentazione dei limiti |
| Overfitting sul test | Risultati non credibili | Split per famiglia, test congelato, tuning sul development |
| Problemi Docker/Elasticsearch durante demo | Demo fallita | Setup semplificato, health check, indice persistente, prova su macchina pulita |
| Scope creep | Ritardo dei deliverable | Must prima di Should/Could, niente nuove tecnologie non motivate |

## 11. Decisioni chiuse e questioni aperte

**Approvate:** approccio B (retrieval classico avanzato), Elasticsearch, Python/FastAPI/Jinja2, monorepo, Docker Compose, uv, framework sperimentale separato, pooling multi-run, tre fonti con ruoli distinti, rubrica 0–2, topic con intent/narrativa, split development/test, confronto controllato dei ranking.

**Da determinare tramite implementazione o audit:** versione patch di Elasticsearch/client e delle librerie; regola definitiva di ammissibilità del corpus; selezione della revisione; cleaning HTML esatto; provenienza della data di pubblicazione; dimensioni reali dei pool e budget annotazione; scelta e accesso effettivo al modello LLM; gestione concreta dei non giudicati nelle metriche; soglie performance; stile finale dell'interfaccia.

Le questioni aperte **non** impediscono il bootstrap del repository, ma vanno trasformate in decisioni esplicite e versionate prima degli esperimenti finali.
