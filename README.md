# Wikinews Search Engine — Homework 4

Monorepo sperimentale per un motore di ricerca **lessicale** delle notizie italiane
Wikinotizie, basato su Elasticsearch, con valutazione IR riproducibile.

## Consegna accademica

[Relazione illustrata su architettura, ricerca e valutazione (PDF)](docs/report/newsfinder.pdf) · [Sorgenti e compilazione](docs/report/README.md)

Il motore cerca in **11.032 articoli** dello snapshot del 20 marzo 2025. Sul test gold di 16 topic il profilo E1, selezionato sul development, raggiunge nDCG@10 **0,6558**. Il campione e la copertura dei giudizi limitano la portata del confronto.

- [Demo e recupero](docs/consegna/demo.md) · [Collaudo](docs/consegna/collaudo.md)
- [Run, qrels e risultati congelati (ZIP)](https://github.com/Forest904/wikinews-search-engine/releases/download/v1.0.0/risultati-m6b.zip)
- [Risultati e limiti](docs/m6b-validation.md) · [Manifest dei risultati](benchmarks/v1/manifests/m6b-production-1.1.json) · [Commit sperimentale](https://github.com/Forest904/wikinews-search-engine/commit/1c6e51d6cf41a515a9b2986d0f7b31768dfd0bd2)

## Documentazione di progetto

- [Benchmark del motore, del server web e dei percorsi browser](docs/performance.md)

- [PRD — requisiti e criteri di accettazione](docs/prd.md)
- [Architettura e struttura dei componenti](docs/architeture.md)
- [Roadmap dalla fase zero alla consegna](docs/roadmap.md)

## Prerequisiti

- Git per clonare il repository
- Python **3.12**
- [`uv`](https://docs.astral.sh/uv/) **0.12.9** (o compatibile con il lockfile)
- Docker Engine / Docker Desktop con Docker Compose v2
- Almeno 4 GB consigliati per Docker in locale. Nel collaudo, checkout, ambiente Python e corpus hanno occupato circa 534 MB complessivi, i due indici circa 128 MB nel volume. Durante la preparazione è stato osservato un database temporaneo di 537 MB. Prevedere anche spazio per immagine Docker e cache degli strumenti.

## Avvio su Windows dopo il primo setup

Per il primo avvio seguire la procedura da clone qui sotto. Per gli avvii successivi fare doppio clic su **Avvia-locale.cmd**, oppure task VS Code **Locale: avvia/riavvia**.
Il sito si apre su `http://127.0.0.1:8000/`; una precedente istanza di questa
checkout viene riavviata. [Comandi, prerequisiti e primo accesso](docs/local-development.md).

## Avvio rapido in ambiente locale

```bash
git clone --branch v1.0.0 https://github.com/Forest904/wikinews-search-engine.git
cd wikinews-search-engine
cp .env.example .env  # PowerShell: Copy-Item .env.example .env
# Modifica ELASTIC_PASSWORD in .env: usa una password locale non banale.
uv sync --locked
# corpus prepare scarica il dump. Se indisponibile, copiare lo snapshot assegnato in data/raw/.

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

Per avviare l'area valutatori senza Elasticsearch, creare gli account e importare
un pacchetto seguendo [la guida M5-B](docs/annotation.md), poi avviare la stessa app
e aprire `/annotate` o `/coordinate`. Il database SQLite è persistente e distinto
dagli indici di ricerca. La guida include fixture, backup e ripristino.

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
nuova directory. Il 19 novembre 2026 la verifica HTTP HEAD sull’URL storico ha restituito 403. In caso di errore usare la copia originale fornita per il corso o richiederla al coordinatore e verificare il checksum indicato nella guida al dataset.

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
  (E1–E4). Default `wikinews_standard_v1` e `wikinews_italian_v1`.
- Ricostruzione esplicita: `uv run --locked wikinews-ir index build --rebuild`.
  Ricrea **entrambi** gli indici configurati; durante il rebuild la ricerca non è garantita.
  Necessaria anche per migrare il vecchio indice M1 contenente cinque fixture.
  Non usare gli indici versionati per scritture esterne: sono bloccati in scrittura.
- Il corpus viene validato prima del bulk; un indice incompleto non viene dichiarato pronto.
  Manifest e diagnostica in `experiments/reports/index-build/` (ignorati da Git).
- Le risorse runtime sono incluse nel wheel e nel container; `configs/` contiene le copie
  leggibili dalla checkout, con test di identità per evitare divergenze.

## Profili avanzati M4

E2 pesa il titolo 3 volte il corpo. E3 aggiunge a E2 fuzzy matching a peso 0.2,
con espansioni limitate; E4 aggiunge a E2 un boost di frase. E3 ed E4 sono
indipendenti: il fuzzy non è attivo in E4. Tutti riutilizzano l'indice italiano,
senza reindicizzazione. Il default resta E0, senza selezione di qualità.

In E4, `energia solare` premia la frase mantenendo i candidati E2;
`"energia solare" Italia` richiede la frase e almeno un termine esterno.
Frasi multiple sono tutte obbligatorie. Sono supportate anche `“virgolette tipografiche”`;
virgolette vuote, annidate o non chiuse producono 422 e un messaggio nella UI.
Le frasi seguono l'analyzer italiano, non un confronto letterale. Negli altri
profili le virgolette non sono operatori. Nessuna sintassi di escape aggiuntiva.

Ogni hit aggiunge `title_segments` e `snippet_segments`, liste di
`{"text":"energia","highlighted":true}`. `title` e `snippet` testuali restano
disponibili. La UI evidenzia i segmenti in sicurezza e usa il testo originale
quando mancano. Il frammento non necessariamente mostra tutti i vincoli della query.

I boost si configurano nei YAML E2–E4 di `configs/retrieval/` e nelle copie
`src/wikinews_ir/resources/retrieval/`: incrementare la versione a ogni modifica
di ranking e mantenere le copie identiche. Le risorse distribuite sono quelle
del pacchetto, senza override per richiesta. Default e limiti in
[ADR 0005](docs/decisions/0005-advanced-retrieval.md). E5 e filtro date rinviati.

## Export TREC e verifica riproducibile

```bash
uv run --locked wikinews-ir runs export --queries configs/smoke/m4-queries.jsonl --output experiments/runs/m4-first --top-k 100
uv run --locked wikinews-ir runs export --queries configs/smoke/queries.jsonl --output experiments/runs/baseline --profiles E0 E1
uv run --locked python scripts/verify_m4.py --output output/m4-check --rebuild
uv run --locked python scripts/verify_m3.py --output output/m3-check --rebuild
```

Usare directory di output nuove. Le query JSONL hanno forma
`{"query_id":"q1","query":"terremoto"}`: ID univoco, non vuoto e senza spazi.
L'export predefinito produce E0.trec–E4.trec e manifest.json; top-k ammesso 1–1.000.
`--profiles` permette un sottoinsieme; i tag TREC includono la versione effettiva.
Il manifest registra anche query senza risultati. I punteggi non vengono alterati:
rispettare rank e tiebreak `document_id` crescente quando si leggono le run.

Gli script verificano riuso, run ripetute e, con `--rebuild`, ricostruzione degli
indici. M3 resta limitato a E0/E1; M4 verifica E0–E4 e gli hash baseline M3,
misura 40 ricerche per profilo dopo warmup e salva i campioni per la review.
Le query smoke non sono topic del benchmark e non alimentano il tuning.
Limiti di cleaning e misure: [report M3](docs/m3-validation.md) e
[report M4](docs/m4-validation.md).

## Licenze

Il codice è distribuito con [licenza MIT](LICENSE). Le condizioni di riutilizzo
**dei contenuti Wikimedia** sono documentate nella [guida al dataset](docs/dataset.md). Il repository non include il dump né articoli del corpus.

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

## Pubblicazione M7-A

Configurazione Hetzner/Cloudflare per `newsfinder.win`:
[decisioni](docs/decisions/0008-operational-deployment.md) e [verifiche](docs/m7a-validation.md).
Usare `compose.production.yaml` separatamente dal Compose locale. Copie manuali
sul PC, nessun backup conservato sulla VPS. Il gate online resta da collaudare.

Per preparare gli embedding con Ollama, importare il pacchetto in Qdrant e attivare il profilo, consultare la [guida alla ricerca semantica](docs/semantic-search.md).
