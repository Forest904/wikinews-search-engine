# ADR 0001 ? Bootstrap M0

Data: 2026-11-16. Decisione: adottata; collaudo locale completato.

## Decisioni

Python 3.12, uv 0.12.9, Elasticsearch 9.5.6 e client Python 9.5.1.
Il client ? limitato alla serie 9.5; uv.lock blocca tutte le dipendenze.
Sviluppo, CI e Docker installano con `uv sync --locked`; Docker esclude il gruppo dev.
La licenza del codice ? MIT (2026 Forest904), distinta dai contenuti Wikimedia.

Manteniamo lo scaffold e la ricerca demo, senza estendere M1.
Un lifespan FastAPI possiede un solo client sincrono per istanza e lo chiude
allo shutdown; la CLI chiude il proprio client anche in caso di errore.
L'iniezione delle dipendenze permette test senza servizi esterni.

`GET /api/health` restituisce 200 con `app=ok, elasticsearch=ready`, oppure
503 con `detail={app: ok, elasticsearch: unavailable}`. Non verifica l'indice.
La verifica usa autenticazione, timeout configurabile positivo e nessun retry.
L'app e la homepage partono anche quando Elasticsearch non ? disponibile.

Compose usa un nodo, heap 1 GB, volume persistente, autenticazione basic e HTTP
senza TLS solo in locale. Le porte host sono vincolate a loopback. L'health check
attende almeno yellow, compatibile con repliche non assegnate su un singolo nodo.
L'app containerizzata ? opzionale con profilo full. TLS e distribuzione pubblica
restano fuori dal perimetro di questo ambiente di sviluppo.

## Alternative e conseguenze

Installazioni non bloccate e rigenerazione automatica del lock nel setup sono
escluse perch? rendono diversi gli ambienti. Un client per richiesta spreca
connessioni; il lifespan ne rende esplicita la propriet?. Un controllo dell'indice
nell'health impedirebbe il collaudo M0 prima del seed e confonderebbe backend e dati.
La CI base resta senza Docker; i test di integrazione sono opt-in con RUN_INTEGRATION=1.

## Verifica

Collaudo locale completato il 2026-11-16:

- `uv sync --locked` in ambiente vuoto e `uv lock --check`: riusciti.
- Ruff: nessun errore; pytest: 21 unit test e 2 test di integrazione passati.
- Build sdist/wheel riuscita; homepage e asset verificati dal wheel installato
  in un ambiente separato, eseguendo fuori dalla checkout.
- Build Docker Linux dal lockfile e avvio Compose full riusciti.
- Health 200 senza indice, 503 con backend fermo, homepage disponibile durante
  il fermo e ritorno a 200 dopo ripristino verificati via HTTP.
- Credenziali errate rifiutate; documento temporaneo conservato dopo ricreazione
  del container Elasticsearch. Indice di prova eliminato al termine.
- Un warning upstream Starlette segnala la deprecazione dell'adapter TestClient
  basato su httpx; non impedisce l'esecuzione dei test.

Il file `.env` locale contiene una password generata e resta ignorato da Git.
I servizi di sviluppo sono lasciati attivi su loopback.
La CI remota richiede la pubblicazione del commit e un'esecuzione GitHub Actions.
