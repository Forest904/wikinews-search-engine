# Wikinews Search Engine — Homework 4

Monorepo sperimentale per un motore di ricerca **lessicale** delle notizie italiane
Wikinotizie, basato su Elasticsearch, con valutazione IR riproducibile.

> **Stato attuale:** **M3 completata e verificata localmente**: 11.032 articoli
> ricercabili con E0/E1, paginazione, dettaglio ed export TREC riproducibile.
> Vedi [report M3](docs/m3-validation.md) e [roadmap](docs/roadmap.md).
> Ranking avanzato e benchmark restano pianificati; CI remota da verificare dopo il push.

## Documentazione di progetto

- [PRD — requisiti e criteri di accettazione](docs/prd.md)
- [Architettura e struttura dei componenti](docs/architeture.md)
- [Roadmap dalla fase zero alla consegna](docs/roadmap.md)

## Prerequisiti

- Python **3.12**
- [`uv`](https://docs.astral.sh/uv/) **0.12.9** (o compatibile con il lockfile)
- Docker Engine / Docker Desktop con Docker Compose v2
- Idealmente almeno 4 GB disponibili per Docker in locale

## Avvio rapido in ambiente locale

```bash
cp .env.example .env
# Modifica ELASTIC_PASSWORD in .env: usa una password locale non banale.
uv sync --locked

docker compose up -d --wait elasticsearch
uv run --locked wikinews-ir corpus prepare
uv run --locked wikinews-ir index build
# Verifica che Elasticsearch sia diventato healthy: docker compose ps
uv run --locked uvicorn wikinews_ir.api.main:app --reload
```

Apri <http://127.0.0.1:8000/> per la pagina iniziale, <http://127.0.0.1:8000/docs>
per OpenAPI, <http://127.0.0.1:8000/api/health> per lo stato dei servizi.
La homepage funziona anche senza backend; health restituisce 200 con backend
raggiungibile e autenticato, 503 altrimenti. Non richiede un indice.
`/api/ready` verifica anche che entrambi gli indici siano pronti e contengano lo stesso
corpus. La preparazione e l'indicizzazione sono job separati dall'avvio Web.
Una seconda esecuzione di `index build` verifica e riusa gli indici già pronti.

**Avvio opzionale full Docker:** dopo aver creato `.env`,
`docker compose --profile full up -d --build --wait` avvia anche il servizio Web.
Questa modalità usa la stessa password di Elasticsearch.

## Qualità del codice

```bash
uv run --locked ruff check .
uv run --locked pytest -q
```

`uv.lock` è versionato: `uv sync --locked` fallisce se manifest e lockfile divergono.
Usare `uv lock` solo per aggiornamenti intenzionali delle dipendenze.
La CI esegue lint e unit test su Ubuntu e Windows con Python 3.12.

I test standard non richiedono Docker. Per il collaudo autenticato:

```bash
RUN_INTEGRATION=1 uv run --locked pytest tests/integration -q
```

In PowerShell:

```powershell
$env:RUN_INTEGRATION = "1"
uv run --locked pytest tests/integration -q
Remove-Item Env:RUN_INTEGRATION
```

## Struttura essenziale

- `src/wikinews_ir/api/`: endpoint FastAPI e Web UI
- `src/wikinews_ir/retrieval/`: query builder e client Elasticsearch condivisi
- `src/wikinews_ir/ingestion/`: pipeline offline, audit e manifest del corpus
- `src/wikinews_ir/evaluation/`: spazio per metriche, run e pooling
- `src/wikinews_ir/adapters/`: integrazioni offline LLM/Wikinotizie
- `configs/`: mapping indice, profili di ricerca, protocollo di valutazione
- `benchmarks/`: topic, qrels e manifest (ancora vuoti)
- `data/raw/`, `data/processed/`: dati locali ignorati da Git
- `experiments/`: risultati locali ignorati da Git
- `docs/`: documenti di progettazione completi

## Dataset vincolato

Dump richiesto dal corso:

<https://dumps.wikimedia.org/other/enterprise_html/runs/20250320/itwikinews-NS0-20250320-ENTERPRISE-HTML.json.tar.gz>

Il file non va inserito in Git. Dalla radice del repository, dopo `uv sync --locked`,
acquisizione, verifica SHA-256 e preparazione si eseguono con un unico comando:

```bash
uv run --locked wikinews-ir corpus prepare
```

Il comando usa `data/raw/` e `data/processed/m2-v1/`; percorsi alternativi con
`--raw-dir` e `--output`. Scarica lo snapshot con User-Agent esplicito e verifica
dimensione e checksum attesi prima di avviare la build. Un archivio locale valido
viene riusato senza rete. Un corpus esistente viene riusato solo dopo verifica
di manifest, versioni, dipendenze e hash degli artefatti. File locali diversi dal
riferimento non vengono sovrascritti: per output incompatibili scegliere una
nuova directory. La disponibilità del download dipende dal server Wikimedia.

I comandi offline restano disponibili per input espliciti; le fixture dei test
sono sintetiche:

```bash
uv run --locked wikinews-ir corpus audit --input data/raw/itwikinews-NS0-20250320-ENTERPRISE-HTML.json.tar.gz --output data/processed/audit-v1
uv run --locked wikinews-ir corpus build --input data/raw/itwikinews-NS0-20250320-ENTERPRISE-HTML.json.tar.gz --output data/processed/m2-v1
```

È supportato anche il NDJSON estratto come `--input`. Le destinazioni devono
essere assenti o vuote: usare una nuova directory per ogni verifica. La build
produce `articles.ndjson`, `manifest.json`, `audit.json` e `decisions.ndjson`.
L'audit produce solo diagnostica e manifest; con errori restituisce exit code 1.
Gli errori strutturali impediscono la pubblicazione della build. I comandi sono
offline e non richiedono Docker o Elasticsearch. Indicizzare poi con `uv run --locked wikinews-ir index build`.

Policy, schema, checksum e verifiche: [dataset](docs/dataset.md) e
[ADR 0003](docs/decisions/0003-corpus-pipeline.md).

## Baseline M3 e API

- E0: BM25 standard; E1: BM25 italiano. Titolo e corpo hanno lo stesso peso;
  query OR, nessun fuzzy/phrase/boost. Default E0, senza selezione di qualità.
- `GET /api/search?q=terremoto&profile=E1&page=1&page_size=10`.
  Query 1–250 caratteri, page_size 1–100, pagina positiva, finestra di 10.000 risultati.
  Il contratto M1 `bm25`/`limit` è stato rimosso.
- Risposta: query, profile, index, hits, total, elapsed_ms, page, page_size, metadata.
  I metadata identificano corpus, indice fisico/UUID, mapping e profilo tramite hash.
  `elapsed_ms` è il tempo del backend; i rank sono assoluti fra pagine.
- `GET /api/articles/{document_id}?profile=E1` e `/articles/{document_id}?profile=E1`
  leggono il dettaglio dallo stesso indice della ricerca. La UI conserva query e pagina.
- Parametri errati: 422; articolo/indice assente: 404; backend indisponibile,
  indice incompleto/incompatibile o ricerca parziale: 503.
- Indici configurabili con `ELASTICSEARCH_INDEX` (E0) e `ELASTICSEARCH_ITALIAN_INDEX`
  (E1). Default `wikinews_standard_v1` e `wikinews_italian_v1`.
- Ricostruzione esplicita: `uv run --locked wikinews-ir index build --rebuild`.
  Ricrea **entrambi** gli indici configurati; durante il rebuild la ricerca non è garantita.
  Necessaria anche per migrare il vecchio indice M1 contenente cinque fixture.
  Non usare gli indici versionati per scritture esterne: sono bloccati in scrittura.
- Il corpus viene validato prima del bulk; un indice incompleto non viene dichiarato pronto.
  Manifest e diagnostica in `experiments/reports/index-build/` (ignorati da Git).
- Le risorse runtime sono incluse nel wheel e nel container; `configs/` contiene le copie
  leggibili dalla checkout, con test di identità per evitare divergenze.

## Export TREC e verifica riproducibile

```bash
uv run --locked wikinews-ir runs export --queries configs/smoke/queries.jsonl --output experiments/runs/m3-first --top-k 100
uv run --locked python scripts/verify_m3.py --output output/m3-check --rebuild
```

Usare directory di output nuove. Le query JSONL hanno forma
`{"query_id":"q1","query":"terremoto"}`: ID univoco, non vuoto e senza spazi.
L'export produce E0.trec, E1.trec e manifest.json; top-k ammesso 1–1.000.
Il manifest registra anche query senza risultati. I punteggi non vengono alterati:
rispettare rank e tiebreak `document_id` crescente quando si leggono le run.

Lo script locale verifica riuso, run ripetute e, con `--rebuild`, ricostruzione degli
indici; misura 50 ricerche per profilo dopo warmup e salva i campioni per la review.
Le dieci query smoke non sono topic del benchmark e non alimentano il tuning.
Limiti di cleaning e misure: [report M3](docs/m3-validation.md).

## Licenze

La licenza del **codice** non è ancora stata scelta. Le condizioni di riutilizzo
**dei contenuti Wikimedia** sono distinte e dovranno essere rispettate nell'eventuale
redistribuzione di dati. Il repository non include il dump né articoli del corpus.

## Setup Windows e comandi operativi

In PowerShell, sostituire `cp` con `Copy-Item .env.example .env`, quindi modificare
la password nel file. Gli altri comandi `uv` e `docker compose` sono identici.
Make è opzionale: `make setup`, `up`, `down`, `serve`, `lint`, `test`, `check`
incapsulano i comandi documentati. `docker compose down` conserva il volume;
non usare `down -v` se si vogliono conservare gli indici.

Se Docker non risponde, avviare Docker Desktop e attendere che `docker info`
riesca. Se Elasticsearch non diventa healthy, controllare `docker compose ps`
e `docker compose logs elasticsearch`, memoria disponibile e credenziali.
Cambiare `ELASTIC_PASSWORD` dopo la prima inizializzazione non aggiorna la password
salvata nel volume: usare le credenziali originarie o la procedura Elastic di reset.
`ES_PORT` è una porta numerica (default 9200), sempre pubblicata su 127.0.0.1;
se cambia, aggiornare anche `ELASTICSEARCH_URL` per l'app eseguita sull'host.

Le decisioni M0 e le evidenze di verifica sono in
[ADR 0001](docs/decisions/0001-bootstrap.md).

## Uso Python e fixture isolate

```python
from wikinews_ir.models import SearchRequest
from wikinews_ir.retrieval.engine import RetrievalEngine

engine = RetrievalEngine()
try:
    results = engine.search(SearchRequest(query="terremoto", profile="E1", page=1, page_size=10))
    print(results.model_dump())
    if results.hits:
        print(engine.get_article(results.hits[0].document_id, "E1").body)
finally:
    engine.close()
```

`uv run --locked wikinews-ir seed-demo` prepara soltanto `wikinews_demo_standard_v1`
e `wikinews_demo_italian_v1`. Per usarli nella UI impostare entrambi i nomi nelle
variabili di ambiente dell'app. Il seed richiede la checkout (`tests/fixtures/`);
non è un comando per importare il corpus. Le fixture sono sintetiche e i loro link
esterni puntano alla homepage Wikinotizie.

Per il collaudo completo con Elasticsearch avviato, in PowerShell:

```powershell
uv run --locked playwright install chromium
$env:RUN_INTEGRATION = "1"
$env:RUN_E2E = "1"
uv run --locked pytest -q
Remove-Item Env:RUN_INTEGRATION
Remove-Item Env:RUN_E2E
```

Su Linux/macOS: `uv run --locked playwright install --with-deps chromium`, poi
`RUN_INTEGRATION=1 RUN_E2E=1 uv run --locked pytest -q`.
I test creano coppie di indici temporanei `test-m3-*` e le eliminano al termine.
Screenshot e trace in `output/playwright/`; la CI li pubblica in caso di fallimento.
Le verifiche automatiche non richiedono il dump reale.
