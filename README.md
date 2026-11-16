# Wikinews Search Engine — Homework 4

Monorepo sperimentale per un motore di ricerca **lessicale** delle notizie italiane
Wikinotizie, basato su Elasticsearch, con valutazione IR riproducibile.

> **Stato attuale:** **M1 completata e verificata localmente**, con ricerca e dettaglio
> su fixture, API condivisa con Python e test browser automatici. Prossimo passo: M2.
> Il nuovo job CI di integrazione/browser è configurato; l'esito remoto è da verificare.
> L'ingestion del dump reale, la ground truth multi-sorgente e il ranking avanzato
> sono **pianificati ma non ancora implementati**. Leggi [la roadmap](docs/roadmap.md).

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
# Verifica che Elasticsearch sia diventato healthy: docker compose ps
uv run --locked uvicorn wikinews_ir.api.main:app --reload
```

Apri <http://127.0.0.1:8000/> per la pagina iniziale, <http://127.0.0.1:8000/docs>
per OpenAPI, <http://127.0.0.1:8000/api/health> per lo stato dei servizi.
La homepage funziona anche senza backend; health restituisce 200 con backend
raggiungibile e autenticato, 503 altrimenti. Non richiede un indice.
Per abilitare la demo opzionale, dalla checkout locale esegui
`uv run --locked wikinews-ir seed-demo`, poi cerca una parola nei cinque articoli
sintetici. Il comando seed usa i file `configs/` e `tests/` della checkout;
non è previsto nel container applicativo o nell'installazione del solo wheel.

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
- `src/wikinews_ir/ingestion/`: spazio per la pipeline sul dump
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

Il file non è incluso nello ZIP né va inserito in Git. La pipeline di download,
normalizzazione, deduplicazione e indicizzazione del corpus reale è prevista in **M2**.
Le fixture sono sintetiche, non un campione reale.

## Scelte e limiti dopo M1

- Immagine Elasticsearch **9.5.6**, client Python **9.5.1** bloccato nel lockfile.
- Trasporto HTTP con basic auth **solo su loopback**, per sviluppo locale.
  Non esporre questo setup su Internet: configurare TLS e hardening per altri ambienti.
- `GET /api/search` supporta inizialmente il solo profilo `bm25`; gli altri file
  in `configs/retrieval/` documentano profili pianificati, non feature già disponibili.
- L'app restituisce **503** quando Elasticsearch non è raggiungibile e **404**
  quando l'indice delle fixture non esiste.
- I qrels umani (gold) e LLM (silver) saranno separati; Wikinotizie sarà
  una baseline esterna, non una fonte di etichette gold.

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

## Vertical slice M1

Eseguire `uv run --locked wikinews-ir seed-demo`, poi aprire la homepage e cercare
`terremoto`: il risultato atteso è **Terremoto in Abruzzo** (`demo-01`). Il titolo
apre il dettaglio locale; il link di ritorno ripristina la query. Anche `soccorsi`
trova lo stesso articolo cercando nel corpo. `zzzznonpresente` mostra lo stato vuoto.
Le [fixture](tests/fixtures/README.md) sono sintetiche; il link esterno nel dettaglio
porta alla homepage Wikinotizie, non a un articolo reale.

- `GET /api/search?q=terremoto&profile=bm25&limit=10`: query normalizzata con trim,
  1–250 caratteri, unico profilo `bm25`, limite 1–100 (default 10).
- `GET /api/articles/demo-01`: ID, titolo, corpo completo e URL.
- `GET /articles/demo-01`: dettaglio HTML; `q` e `profile` conservano la ricerca di ritorno.
- Parametri non validi: 422; articolo/indice assente: 404 con messaggi distinti;
  backend indisponibile: 503. Health verifica la connessione, non l'esistenza dell'indice.

Lo stesso motore è utilizzabile da Python:

```python
from wikinews_ir.models import SearchRequest
from wikinews_ir.retrieval.engine import RetrievalEngine

engine = RetrievalEngine()
try:
    results = engine.search(SearchRequest(query="terremoto"))
    print(results.model_dump())
    print(engine.get_article("demo-01").body)
finally:
    engine.close()
```

Per la verifica completa, con Elasticsearch avviato:

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
I test creano indici temporanei `test-m1-*` e li eliminano al termine; i server
browser usano porte libere. Non occorre caricare prima le fixture nell'indice demo.
Screenshot e trace sono salvati in `output/playwright/` (ignorato da Git);
la CI li pubblica come artefatti in caso di fallimento.

Evidenze e confini della milestone: [ADR 0002](docs/decisions/0002-vertical-slice.md).
