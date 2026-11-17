# Sviluppo locale su Windows

## Avvio quotidiano

Doppio clic su **Avvia-locale.cmd** nella radice del progetto, oppure in VS Code:
**Terminale → Esegui attività → Locale: avvia/riavvia**.

Il comando avvia il codice di questa checkout e apre **http://127.0.0.1:8000/**
nel browser predefinito dopo che l'applicazione è pronta. Se esiste già una sua
istanza locale, la arresta e la riavvia. Non apre il sito pubblico.

Prerequisiti: Windows PowerShell, Python/uv disponibili e Docker Desktop per
Elasticsearch. Il file `.env` deve contenere le credenziali locali già usate dal
volume Elasticsearch; non cambiare la password di un volume esistente.

```powershell
.\scripts\local-start.ps1
.\scripts\local-start.ps1 -Page valutazione
.\scripts\local-start.ps1 -Page coordinamento -Port 8001
.\scripts\local-start.ps1 -NoBrowser
.\scripts\local-status.ps1
.\scripts\local-stop.ps1
```

Se la policy blocca gli script, usare il file CMD o le task: applicano `Bypass`
soltanto al processo PowerShell, senza cambiare le impostazioni permanenti.
Gli script funzionano anche quando lanciati da una directory diversa.

## Comportamento

- Sincronizza le dipendenze dal lockfile e usa `.venv/Scripts/python.exe`.
- Riutilizza Elasticsearch locale; se non è in ascolto avvia soltanto il servizio
  Elasticsearch di `compose.yaml`. Se Docker non risponde, il comando avvia
  automaticamente Docker Desktop (oppure ne attende l'avvio già in corso) e
  aspetta fino a 120 secondi che il motore sia pronto prima di eseguire Compose.
- Mantiene corpus e nomi degli indici configurati. Non scarica il dump, non
  ricostruisce indici e non importa la preview. Se la ricerca non è pronta,
  mostra il comando `uv run --locked wikinews-ir index build` da eseguire dopo
  aver verificato configurazione e disponibilità del corpus.
- Usa `data/annotation/annotation.sqlite3`, inizializzato al primo avvio e
  conservato ai successivi. Forza cookie non Secure soltanto nel processo locale.
- Python si ricarica automaticamente; dopo modifiche a HTML/CSS/JavaScript
  ricarica il browser (Ctrl+F5 se necessario). Non è un live reload del browser.
- Log e stato sono in `output/local/`, esclusi da Git. L'arresto termina anche
  il reloader e i processi figli, ma lascia Elasticsearch e i dati intatti.
- Una sola istanza gestita per checkout: cambiare porta riavvia quella precedente.
  L'apertura del browser può creare una nuova scheda; non chiude le schede esistenti.
- Una porta occupata da un processo estraneo o non identificabile produce un
  errore con PID. Non viene terminato. Un'istanza manuale è riconosciuta solo se
  usa il Python della `.venv` di questa checkout e il modulo Uvicorn dell'app.

## Primo accesso alla Valutazione

Il database nuovo non contiene account o assegnazioni. Crea il coordinatore:

```powershell
uv run --locked wikinews-ir annotation --db data/annotation/annotation.sqlite3 create-user coordinatore --coordinator
```

La password viene chiesta senza mostrarla. Importa poi un pacchetto locale:

```powershell
uv run --locked wikinews-ir annotation --db data/annotation/annotation.sqlite3 import --packet PERCORSO_PACCHETTO
```

Segui [la guida di annotazione](annotation.md) per altri utenti e assegnazioni.
Non è necessario creare account per provare la ricerca.

## Quando le modifiche sono pronte

1. Avvia in locale, modifica e verifica nel browser.
2. Esegui lint e test pertinenti: `uv run --locked ruff check .` e
   `uv run --locked pytest -q` (i test browser richiedono i flag documentati).
3. Crea un commit e fai push quando vuoi pubblicare le modifiche.

Il push su `main` attiva il deploy esistente dopo i controlli CI, come descritto
in [deployment.md](deployment.md). Questi script non fanno push, non accedono
via SSH al server e non eseguono deploy. Le modifiche infrastrutturali seguono
la procedura separata documentata nella guida di deployment.

## Modalità mock per esplorare la UI

```powershell
.\scripts\local-start.ps1 -Mock -Page coordinamento
```

Richiede il coordinatore locale `luca`. Mantiene le sue credenziali e aggiunge un
pacchetto chiaramente marcato MOCK, due valutatori fittizi, attività in stati
diversi, revisioni assegnate e pendenti, blocchi attivi e in bozza e dati esportabili
per calibrazione e sviluppo. Gli account fittizi servono a popolare i flussi;
non è necessario accedervi. Nessun dato di test viene rilasciato automaticamente.

La ricerca usa esclusivamente gli indici `wikinews_demo_standard_v1` e
`wikinews_demo_italian_v1`. Prova **terremoto**, **calcio** o **italiana**.
Il corpus reale non viene modificato. Un avvio senza `-Mock` torna agli indici
configurati in `.env`; il pacchetto MOCK rimane nel database locale.

La preparazione è ripetibile e non sovrascrive i giudizi già presenti. Prima di
popolare il database crea una copia in `output/local/before-mock-*.sqlite3`.

### Catalogo delle pagine articolo

Dalla radice del repository, passare a questo comando il percorso del dump originale e la directory del corpus corrispondente:

```sh
python -m wikinews_ir.reader_build --dump <dump.tar.gz> --corpus data/processed/m2-v1
```

Il catalogo viene pubblicato in `data/reader/catalog.sqlite3`. Usare `--pilot --output output/reader/pilot.sqlite3` per provare un campione di 100 revisioni. Per aggiornare i crediti in un catalogo già costruito, eseguire:

```sh
python -m wikinews_ir.reader_build --enrich-only --user-agent "NewsFinder/1.0 (contatto del gestore)"
```

La preparazione riporta il numero di pagine strutturate, figure candidate e immagini con crediti. Le richieste Wikimedia fallite restano da recuperare. Il lettore mostra una figura solo quando dispone dei suoi crediti. Il browser recupera la miniatura da Wikimedia. In produzione collocare il catalogo in `/opt/newsfinder/imports/reader/catalog.sqlite3`; per altre installazioni configurare `READER_CATALOG`. Il lettore usa il testo indicizzato se il catalogo manca o appartiene a un’altra revisione del corpus.
