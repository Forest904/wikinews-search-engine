# Architettura del sistema consegnato

## Dal dump alla ricerca

Il job di ingestione legge il tar.gz Enterprise HTML, seleziona una revisione per pagina e produce articoli NDJSON con ID stabile, testo, data e provenienza. Il manifest lega il corpus alle regole di preprocessing e ai checksum. Il job di indicizzazione crea due indici fisici Elasticsearch sullo stesso corpus. E0 interroga wikinews_standard_v1 ed E1–E4 interrogano wikinews_italian_v1. La costruzione verifica i documenti prima del riuso di un indice. [Dataset](dataset.md) · [Decisione sugli indici](decisions/0004-baseline-corpus.md)

Il browser interroga FastAPI. UI, API ed export delle run usano il medesimo motore lessicale. E0 ed E1 isolano l’effetto dell’analyzer. E2 aggiunge peso al titolo, E3 la tolleranza ai refusi ed E4 una clausola di frase. Il lettore espone una pagina locale per ID. Il catalogo SQLite opzionale arricchisce navigazione e impaginazione. La modalità live interroga Wikimedia, quella semantica usa Ollama e Qdrant. Il benchmark M6-B confronta E0–E4 e la run Wikimedia archiviata. [Profili](decisions/0005-advanced-retrieval.md) · [Lettore](local-development.md) · [Ricerca semantica](semantic-search.md)

## Dai giudizi ai risultati

L’applicazione di annotazione salva assegnazioni, giudizi indipendenti e revisione in SQLite. Gli export gold e silver restano separati. Le run TREC ordinano ID del corpus per topic. La valutazione offline combina run, split e giudizi, congela il profilo sul development e registra il test finale. La pubblicazione operativa usa Docker Compose e Caddy. La demo accademica usa Elasticsearch locale e FastAPI su loopback. [Annotazione](annotation.md) · [Valutazione](evaluation.md) · [Deployment](deployment.md)


## Confini di persistenza e guasti

| Componente | Dati persistiti | Comportamento operativo |
|---|---|---|
| Preprocessing | Archivio, corpus NDJSON e manifest sul filesystem | Un checksum incompatibile interrompe il riuso. Ripartire in una directory vuota con lo snapshot verificato. |
| Elasticsearch | Due indici versionati nel volume Compose | Health verifica la connessione autenticata. Readiness controlla anche la disponibilità degli indici sullo stesso corpus. |
| Lettore | Catalogo SQLite opzionale | Il dettaglio per ID può visualizzare l’articolo dall’indice anche senza arricchimento multimediale. |
| Annotazione | Account, giudizi e storico in un database SQLite dedicato | La raccolta e il ripristino hanno un ciclo di vita indipendente dagli indici. |
| Esperimenti | Topic versionati, qrels, run TREC, report e manifest | I report congelati si consultano offline. I checksum collegano gli artefatti alla valutazione originale. |

Il progetto iniziale è consultabile nel [blueprint storico](https://github.com/Forest904/wikinews-search-engine/blob/1c6e51d6cf41a515a9b2986d0f7b31768dfd0bd2/docs/architeture.md). Le decisioni implementate sono raccolte nel [registro ADR](decisions/README.md).
