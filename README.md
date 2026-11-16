# Wikinews Search Engine — Homework 4

Monorepo sperimentale per un motore di ricerca **lessicale** delle notizie italiane
Wikinotizie, basato su Elasticsearch, con valutazione IR riproducibile.

> **Stato attuale:** scaffold iniziale/M0 con un percorso dimostrativo su fixture.
> L'ingestion del dump reale, la ground truth multi-sorgente e il ranking avanzato
> sono **pianificati ma non ancora implementati**. Leggi [la roadmap](docs/roadmap.md).

## Documentazione di progetto

- [PRD — requisiti e criteri di accettazione](docs/prd.md)
- [Architettura e struttura dei componenti](docs/architeture.md)
- [Roadmap dalla fase zero alla consegna](docs/roadmap.md)

## Prerequisiti

- Python **3.12**
- [`uv`](https://docs.astral.sh/uv/) **0.10.0** (o compatibile con il lockfile)
- Docker Engine / Docker Desktop con Docker Compose v2
- Idealmente almeno 4 GB disponibili per Docker in locale

## Avvio rapido in ambiente locale

```bash
cp .env.example .env
# Modifica ELASTIC_PASSWORD in .env: usa una password locale non banale.
uv lock
uv sync

docker compose up -d elasticsearch
# Verifica che Elasticsearch sia diventato healthy: docker compose ps
uv run wikinews-ir seed-demo
uv run uvicorn wikinews_ir.api.main:app --reload
```

Apri <http://127.0.0.1:8000/> per la pagina iniziale, <http://127.0.0.1:8000/docs>
per OpenAPI, <http://127.0.0.1:8000/api/health> per lo stato dei servizi.
Cerca nell'indice di fixture digitando una parola presente nei cinque articoli
sintetici. Nessuna notizia del dump reale viene caricata in questo passaggio.

**Avvio opzionale full Docker:** dopo aver creato `.env`,
`docker compose --profile full up -d --build` avvia anche il servizio Web.
Questa modalità usa la stessa password di Elasticsearch.

## Qualità del codice

```bash
uv run ruff check .
uv run pytest -q
```

`uv.lock` **non è ancora incluso**: non è stato possibile risolvere le dipendenze
nell’ambiente di generazione (accesso al package index non disponibile).
Il comando `uv lock`, eseguito sulla tua macchina con accesso a PyPI, produrrà
il vero lockfile da committare prima della prima release. La build Docker
iniziale usa `pip install .` e sarà convertita a una build bloccata dopo M0.

I test standard non richiedono Docker; i test di integrazione con Elasticsearch
saranno aggiunti nelle milestone successive.

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

## Scelte e limiti di questo scaffold

- Immagine Elasticsearch **9.5.6**, pin iniziale da verificare nell'ambiente target.
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
