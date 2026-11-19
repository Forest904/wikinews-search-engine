# Gestione operativa

## Sviluppo locale

### Avvio quotidiano

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

### Comportamento

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

### Primo accesso alla Valutazione

Il database nuovo non contiene account o assegnazioni. Crea il coordinatore:

```powershell
uv run --locked wikinews-ir annotation --db data/annotation/annotation.sqlite3 create-user coordinatore --coordinator
```

La password viene chiesta senza mostrarla. Importa poi un pacchetto locale:

```powershell
uv run --locked wikinews-ir annotation --db data/annotation/annotation.sqlite3 import --packet PERCORSO_PACCHETTO
```

Segui [la guida di annotazione](operazioni.md#annotazione) per altri utenti e assegnazioni.
Non è necessario creare account per provare la ricerca.

### Quando le modifiche sono pronte

1. Avvia in locale, modifica e verifica nel browser.
2. Esegui lint e test pertinenti: `uv run --locked ruff check .` e
   `uv run --locked pytest -q` (i test browser richiedono i flag documentati).
3. Crea un commit e fai push quando vuoi pubblicare le modifiche.

Il push su `main` attiva il deploy esistente dopo i controlli CI, come descritto
in [Deployment](#deployment). Questi script non fanno push, non accedono
via SSH al server e non eseguono deploy. Le modifiche infrastrutturali seguono
la procedura separata documentata nella guida di deployment.

### Modalità mock per esplorare la UI

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

#### Catalogo delle pagine articolo

Dalla radice del repository, passare a questo comando il percorso del dump originale e la directory del corpus corrispondente:

```sh
python -m wikinews_ir.reader_build --dump <dump.tar.gz> --corpus data/processed/m2-v1
```

Il catalogo viene pubblicato in `data/reader/catalog.sqlite3`. Usare `--pilot --output output/reader/pilot.sqlite3` per provare un campione di 100 revisioni. Per aggiornare i crediti in un catalogo già costruito, eseguire:

```sh
python -m wikinews_ir.reader_build --enrich-only --user-agent "NewsFinder/1.0 (contatto del gestore)"
```

Per recuperare posizione, formato e dimensioni di tutte le figure da un catalogo precedente, rieseguire la preparazione dal dump. Il comando riutilizza i crediti esistenti e pubblica il catalogo con sostituzione atomica. Il riepilogo conta le pagine strutturate, i file candidati distinti e quelli con crediti. Le richieste Wikimedia fallite restano da recuperare. Il lettore mostra una figura solo quando dispone dei suoi crediti. Il browser recupera la miniatura da Wikimedia. In produzione collocare il catalogo in `/opt/newsfinder/imports/reader/catalog.sqlite3`; per altre installazioni configurare `READER_CATALOG`. Il lettore usa il testo indicizzato se il catalogo manca o appartiene a un’altra revisione del corpus.


### Ricerca live e accesso a Wikimedia

In **Filtri > Modalità di ricerca > Cerca su Wikinotizie**, la ricerca usa il sito corrente.
Il titolo apre la copia in archivio quando disponibile. La fonte della miniatura segue la vista:
pagina corrente nei risultati live, figura della revisione del dump nel lettore locale.

Il backend espone `GET /api/search/live?q=Sicilia`. Passare il valore opaco di `next_cursor`
come `cursor` per la pagina successiva. Le pagine contengono fino a dieci risultati e sono
memorizzate per due minuti per processo. Le immagini e il collegamento locale sono facoltativi.
Un errore temporaneo della ricerca restituisce HTTP 503.

Servizio, benchmark e catalogo usano `WIKIMEDIA_USER_AGENT`. Il valore predefinito identifica
NewsFinder e indica la pagina delle issue del progetto come contatto. Le CLI accettano anche
`--user-agent`. Per aggiornare i metadati delle immagini nel catalogo locale:

```powershell
uv run --locked python -m wikinews_ir.reader_build --enrich-only
```

La procedura conserva i crediti esistenti e riprende i lotti con errori temporanei.
I file privi di crediti utilizzabili tornano verificabili dopo sette giorni.

## Annotazione

### Avvio locale e account

```powershell
uv sync --locked
uv run --locked wikinews-ir annotation init
uv run --locked wikinews-ir annotation create-user valutatore-1 --coordinator
uv run --locked wikinews-ir annotation create-user valutatore-2
uv run --locked wikinews-ir annotation create-user valutatore-3
```

Ogni comando chiede una password di almeno 10 caratteri senza mostrarla. Non ci
sono credenziali predefinite. Per automazione, `--password-env NOME_VARIABILE`
legge la password dalla variabile indicata, senza scriverla nei log o negli
argomenti del processo. `reset-password <utente>` usa gli stessi meccanismi e
revoca tutte le sessioni dell'utente. Il coordinatore può anche annotare.

Il database predefinito è `data/annotation/annotation.sqlite3`, ignorato da Git.
`ANNOTATION_DB` configura il percorso usato dall'app; per i comandi si può usare
`annotation --db <percorso> <comando>`. CLI e app devono puntare allo stesso file.

```powershell
# Fixture sintetiche: un topic di calibrazione, quattro documenti, nessun giudizio.
uv run --locked wikinews-ir annotation demo-packet --output output/m5b-demo-packet
uv run --locked wikinews-ir annotation import --packet output/m5b-demo-packet
uv run --locked uvicorn wikinews_ir.api.main:app --reload
```

Aprire <http://127.0.0.1:8000/coordinate> con l'account coordinatore e
<http://127.0.0.1:8000/annotate> con gli account dei valutatori. Per sessioni
simultanee usare profili browser distinti. Il pacchetto demo non è il pilot reale.
Il comando `demo-packet` richiede una directory nuova; l'import dello stesso
pacchetto è idempotente.

Per dati reali, importare la directory prodotta da `benchmark packet`. L'import
verifica tipo, manifest, checksum, schema, riferimenti e hash dei testi. Topic
test richiedono un protocollo `frozen`. Testi e rubriche importati non vengono
aggiornati dal corpus o dal Web: una modifica richiede un nuovo pacchetto.

#### Avvio Docker

Il servizio `app` monta il volume `annotation-data` e può avviarsi senza aspettare
Elasticsearch. Dopo la configurazione `.env` descritta nel README:

```powershell
docker compose --profile full up -d --build app
docker compose exec app wikinews-ir annotation init
docker compose exec app wikinews-ir annotation create-user valutatore-1 --coordinator
```

Per importare un pacchetto dall'host, copiarne la directory nel container con
`docker compose cp <directory-pacchetto> app:/tmp/pacchetto`, poi eseguire
`docker compose exec app wikinews-ir annotation import --packet /tmp/pacchetto`.
Il database del container è `/app/data/annotation/annotation.sqlite3`; è distinto
dal database host. `docker compose down` conserva il volume; `down -v` lo elimina.

Il coordinatore importa il pacchetto congelato, assegna le coppie, controlla la copertura e rivede i disaccordi. Il valutatore lavora sulle proprie assegnazioni, salva i giudizi e può riprendere la sessione. Esportare gold e silver separatamente e mantenere il test riservato durante il tuning.

### Export e separazione del test

Il coordinatore scarica uno ZIP per pacchetto e split. Contiene:

- `packet.json`, limitato allo split scelto;
- `source_manifest.json`, con la provenienza del pacchetto importato;
- `judgments.jsonl`, con originali correnti delle sole coppie finalizzate e una finale per coppia;
- `qrels_gold.tsv` e relativo manifest M5-A;
- `history.jsonl`, `decisions.jsonl`, `assignments.jsonl` e provenienza delle finali;
- `manifest.json`, con checksum, pacchetto sorgente, autore, split e conteggi.

Il file `judgments.jsonl` passa lo stesso validatore/exporter gold M5-A. Le revisioni
superate sono nel file di cronologia, non contate come annotatori aggiuntivi.
La finalizzazione automatica usa l'identificativo esplicito
`system:auto-consolidation`; il file di provenienza dichiara `method=automatic`
e `reviewer=null`, senza inventare un revisore umano.

Le astensioni finali sono escluse dai qrels; le coppie pendenti o mai giudicate
restano unjudged, con conteggi nel manifest. Nessuna conversione in grado zero.
Gli export ordinari sono calibration/development. Il test richiede una scelta
esplicita e una conferma registrata nell'audit; annotarlo non ne autorizza l'uso
nel tuning. Non esistono collegamenti automatici con metriche o selezione dei profili.

### Persistenza, backup e aggiornamenti

SQLite usa WAL, foreign key, transazioni e versionamento dello schema. Il target
è un singolo server con archivio locale persistente, non un file condiviso via rete.
Tutti i salvataggi confrontano una versione attesa; richieste concorrenti incompatibili
ricevono HTTP 409. Riavviare l'app non cancella pacchetti, giudizi o cronologia.

```powershell
uv run --locked wikinews-ir annotation backup --output output/annotation-backup.sqlite3
# Ripristino in un NUOVO percorso, senza sovrascrivere l'archivio corrente:
uv run --locked wikinews-ir annotation --db output/restored.sqlite3 restore --input output/annotation-backup.sqlite3
```

Il backup usa l'API SQLite, includendo i dati nel WAL, e verifica `integrity_check`.
La destinazione deve essere nuova. Il ripristino verifica la versione dello schema.
Per provarlo, arrestare l'app locale, impostare `ANNOTATION_DB` sul file ripristinato,
riavviare e verificare account, avanzamento e cronologia. Per il container eseguire
il backup con `docker compose exec app ...`, poi copiarlo sull'host con
`docker compose cp`. Conservare i backup con gli stessi permessi del database.

Prima di aggiornare l'app, effettuare un backup; il codice rifiuta database con
versione più recente di quella supportata. Non ricreare il volume durante un
aggiornamento. Un errore HTTP 503 di salvataggio richiede di controllare spazio,
permessi del percorso e log dell'app, poi riprovare senza perdere il modulo.

Le password sono hash scrypt; i cookie di sessione sono HttpOnly/SameSite, con
scadenza di 12 ore, token CSRF e revoca al logout/reset. Il limite dei tentativi di
login è persistente. Per HTTPS impostare `ANNOTATION_COOKIE_SECURE=1` e configurare
correttamente il proxy di M7-A. Le risposte dell'area riservata non sono memorizzabili
in cache; i contenuti degli articoli vengono inseriti come testo, senza HTML eseguibile.

## Deployment

Il workflow `ci.yml` richiama `deploy.yml` dopo tutti i test, esclusivamente
per push su `main`. GitHub costruisce l'immagine Linux amd64 e la trasferisce
via SSH alla VPS; non occorre un registry o un runner installato sul server.
Le esecuzioni sono serializzate e un commit superato da un nuovo push viene
saltato prima di sostituire l'applicazione.

### Attivazione

In GitHub, Settings → Secrets and variables → Actions, aggiungere:

| Secret | Valore per il server attuale |
| --- | --- |
| `DEPLOY_HOST` | `2.29.176.129` |
| `DEPLOY_USER` | `root` |
| `DEPLOY_SSH_KEY` | Contenuto completo della chiave privata SSH, senza passphrase |
| `DEPLOY_KNOWN_HOSTS` | Riga verificata di known_hosts per il server |

La chiave locale è `$HOME/.ssh/newsfinder`. Se protetta da passphrase, creare
una chiave dedicata ad Actions e aggiungerne la pubblica a `authorized_keys`.
Non inserire mai la chiave privata nel repository. Per copiare i valori negli
appunti da PowerShell senza stamparli:

```powershell
Get-Content -Raw "$HOME/.ssh/newsfinder" | Set-Clipboard
ssh-keygen -F 2.29.176.129 -f "$HOME/.ssh/known_hosts" |
    Where-Object { $_ -notmatch '^#' } | Set-Clipboard
```

Eseguire i due comandi separatamente, incollando ogni valore nel relativo secret.
Il secondo usa l'identità del server già verificata localmente, senza accettare
automaticamente una nuova host key durante il deploy.

Il job usa l'environment `production`; se si configura un'approvazione obbligatoria
su questo environment, il deploy attenderà l'approvazione. Per un flusso automatico
non impostare tale requisito. Committare e pubblicare i file su `main` per attivare
il flusso; verificarne la prima esecuzione nella scheda Actions.

### Comportamento e limiti

- Il deploy aggiorna il container `app` usando l'immagine `newsfinder-app:<SHA>`.
  Una breve interruzione durante la sostituzione del container è prevista.
- Usa il Compose già presente in `/opt/newsfinder/current`, i segreti in
  `/opt/newsfinder/production.env` e i volumi esistenti. Non aggiorna il checkout
  del server: modifiche a Compose, Caddy e infrastruttura richiedono un intervento
  esplicito, separato dal deploy dell'applicazione.
- Verifica la compatibilità del database prima della sostituzione, poi la salute
  HTTP, il database di annotazione e la connessione a Elasticsearch. Non esegue
  migrazioni automatiche né reindicizzazione del corpus.
- Se i controlli falliscono, tenta il ripristino dell'immagine precedente e
  segnala il fallimento in Actions. Non è un rollback dei dati o dello schema.
- `/opt/newsfinder/deployed-revision` viene aggiornato solo dopo i controlli.
  `bash scripts/server.sh status` e `compose` leggono questo riferimento.
- Le immagini precedenti sono conservate per il rollback. Controllare lo spazio
  con `docker system df` e rimuovere periodicamente solo i tag non più necessari,
  conservando l'immagine attiva e almeno quella precedente. Non cancellare i volumi.
- La porta SSH deve essere raggiungibile dai runner GitHub; l'accesso dal PC è
  stato verificato, quello dai runner richiede la prima esecuzione reale.

### Ripristino manuale

Sul server, scegliere lo SHA di un'immagine precedente disponibile:

```bash
cd /opt/newsfinder/current
export APP_IMAGE=newsfinder-app:SHA_PRECEDENTE
bash scripts/server.sh compose up -d --no-deps --no-build --wait app
bash scripts/server.sh compose exec -T app python -m wikinews_ir.operations check
printf '%s\n' SHA_PRECEDENTE > /opt/newsfinder/deployed-revision
```

Le migrazioni richiedono una procedura dedicata con copia manuale su PC e
verifica del ripristino, come concordato in ADR 0008.

## Ricerca semantica

La modalità **Ricerca semantica** ordina per similarità coseno tra la query e titolo/apertura. Il profilo HTTP è `semantic`. Il lettore continua ad aprire la revisione dell'archivio Elasticsearch. Il testo mostrato al lettore e gli offset delle annotazioni provengono dal corpus originale.

### Preparazione e prova locale

Con Ollama in esecuzione sull'host e il modello `qwen3-embedding:0.6b` disponibile, avviare Qdrant con `docker compose --profile semantic up -d qdrant`. La CLI eseguita sull'host usa le porte locali 11434 e 6333. Le variabili `OLLAMA_URL` e `QDRANT_URL` consentono di scegliere gli indirizzi. L'app in Compose usa il nome del servizio Qdrant e raggiunge Ollama tramite `host.docker.internal`.

Dal repository, per l'anteprima e la calibrazione sui documenti selezionati nel pilota:

~~~sh
uv run wikinews-ir semantic preview --corpus data/processed/m2-v1 --limit 5
uv run wikinews-ir semantic generate --corpus data/processed/m2-v1 --selection benchmarks/pilot/selection-v1.jsonl --package data/processed/semantic-qwen3-06b-natural
uv run wikinews-ir semantic generate --corpus data/processed/m2-v1 --selection benchmarks/pilot/selection-v1.jsonl --variant stem --package data/processed/semantic-qwen3-06b-stem
uv run wikinews-ir semantic import --check-archive --package data/processed/semantic-qwen3-06b-natural
uv run wikinews-ir semantic import --check-archive --package data/processed/semantic-qwen3-06b-stem
uv run wikinews-ir semantic verify --package data/processed/semantic-qwen3-06b-natural
~~~

L'input di partenza è `articles.ndjson` con manifest. Il generatore usa la provenienza di ciascuna revisione per riprendere l'HTML esatto nel dump, eliminare figure/didascalie e applicare le regole editoriali dell'ingestione. Per un dump in un'altra directory specificare `--raw PATH`. Il tokenizer viene ricostruito da vocabolario e merge del GGUF installato. La CLI conserva input esatto e numero di token per ogni vettore. Il pacchetto è indipendente dal filesystem e dall'architettura della macchina. Ripetere lo stesso comando per riprendere un build interrotto. Dopo una modifica alla pulizia, `--reuse PACCHETTO_PRECEDENTE` riusa i vettori degli input identici nello stesso batch se il modello e il runtime corrispondono.

Per costruire il pacchetto dell'intero archivio, omettere `--selection` e usare una nuova directory. L'import crea una collezione, verifica i punti e commuta l'alias in un'unica operazione. Restituisce i nomi della collezione attiva e di quella precedente. La variante con stemming usa un alias separato.

### Valutazione

Con i due pacchetti importati e il profilo italiano Elasticsearch costruito sul medesimo corpus:

~~~sh
uv run python scripts/benchmark_semantic.py --queries benchmarks/topics/calibration-draft.jsonl --qrels experiments/runs/pilot-qrels-silver-001/qrels_silver.tsv --natural data/processed/semantic-qwen3-06b-natural --stem data/processed/semantic-qwen3-06b-stem --output experiments/reports/semantic-qwen3-06b.json
~~~

Il report limita i candidati E1 agli stessi articoli presenti in Qdrant e conserva le statistiche lessicali del corpus E1. Riporta nDCG@10, numero di risultati giudicati, ID da revisionare e tempi per query. I giudizi silver sono stime. Le query senza documenti rilevanti giudicati nel campione hanno nDCG indefinito. La variante indicizzata richiede a Qdrant la normale ricerca approssimata e misura la sovrapposizione con la ricerca esatta. Su collezioni piccole Qdrant può scegliere una scansione completa. Il profilo pubblico usa per default la ricerca esatta del pilota. Per usare la ricerca indicizzata impostare `SEMANTIC_EXACT=0`.

#### Esito della calibrazione locale

Il confronto del 18 novembre 2026 usa i 24 articoli selezionati e le quattro query di calibrazione, con giudizi silver. La ricerca avviene sugli stessi candidati per tutti i profili.

| Profilo | nDCG@10 medio | Risultati giudicati nei primi 10 |
| --- | ---: | ---: |
| Elasticsearch E1 | 0,952 | 23 su 35 |
| Qwen2.5 3B su testo naturale | 0,349 | 13 su 40 |
| Qwen2.5 3B con stemming | 0,322 | 13 su 40 |

Nel precedente esperimento con Qwen2.5 3B, per la query sul terremoto in Abruzzo il profilo naturale ha collocato al primo posto la notizia della morte di Sergio Endrigo. Il testo naturale rimane il profilo semantico selezionabile per il pilota. Elasticsearch resta il motore predefinito. Con il contesto impostato a 2.048 token, Ollama ha riportato un ingombro locale di 2,0 GB per il modello.

### Attivazione e server

#### Query elaborate dal PC Windows

Il PC apre una connessione SSH uscente verso la VPS e la ristabilisce quando cambia rete. Sul PC il relay accetta soltanto lo stato del modello e un singolo embedding di query per richiesta. Sul server il container usa `OLLAMA_URL=unix:///imports/ollama-query/ollama.sock`. Il socket è disponibile tramite il volume degli import già montato. Il PC deve essere acceso, connesso, con la sessione Windows avviata e Ollama disponibile.

La configurazione del server è in `deploy/install-ollama-query.sh`. Lo script riceve come argomento il campo base64 della chiave pubblica dedicata `newsfinder-query.pub`, prepara un account SSH limitato e un socket systemd e imposta l'URL in `/opt/newsfinder/production.env`. Il collegamento Windows si avvia con `.\scripts\start-ollama-query.ps1 -AtLogon`. Il collegamento **NewsFinder Ollama** nella cartella Esecuzione automatica lo riavvia ai successivi accessi. Il log di riconnessione è in `output/ollama-query/tunnel.log`.

Per verificare il percorso completo dalla VPS, dalla root del repository in PowerShell:

~~~powershell
Get-Content -Raw scripts/check-ollama-query.py | ssh -i "$env:USERPROFILE/.ssh/newsfinder" root@2.29.176.129 docker exec -i newsfinder-app-1 python -
~~~

Per monitorare il corpus completo usare `.\scripts\embedding-status.ps1 -Watch`. Il conteggio indica le righe dei batch salvati e viene aggiornato ogni 30 secondi. Ctrl+C chiude il monitor. Senza `-Watch` viene stampato un solo aggiornamento.

La VPS descritta in ADR 0008 dispone di 2 GB di RAM condivisi con Elasticsearch. Prima di avviare Ollama sullo stesso host misurare il fabbisogno del modello su una macchina di prova. Per tenere il modello su un host privato dedicato impostare `OLLAMA_URL` nell'ambiente di produzione e avviare soltanto Qdrant sulla VPS.

1. Distribuire il Compose di produzione aggiornato nello stesso checkout usato dal deploy. Mantenere inizialmente `SEMANTIC_ENABLED=0`. Il workflow di deploy dell'app usa il Compose già presente sulla VPS.
2. Avviare `qdrant` e `ollama` con `docker compose --env-file /opt/newsfinder/production.env -f compose.production.yaml --profile semantic up -d qdrant ollama`. Entrambi usano la rete backend interna. Copiare nel volume Ollama il manifest e i blob del modello locale con lo stesso digest, per esempio mediante `docker compose ... cp` nella directory `/root/.ollama/models`. Verificare con `exec ollama ollama list`.
3. Per importare un pacchetto preparato sul PC, copiarlo in `/opt/newsfinder/imports/semantic`. Eseguire nel container app `wikinews-ir semantic import --check-archive --package /imports/semantic` e `wikinews-ir semantic verify --package /imports/semantic`. Per generare sul server, montare il corpus e il dump in `/imports` e usare `semantic generate --corpus /imports/corpus --raw /imports/dump.tar.gz --package /reports/semantic` in un job con memoria sufficiente. Il volume `/reports` è scrivibile. Usare la stessa versione di Ollama indicata dal manifest.
4. Verificare che il checksum del corpus coincida con quello dell'archivio Elasticsearch, quindi interrogare `/api/search?q=terremoto&profile=semantic`, anche con intervallo di anni. Aprire una scheda e tornare ai risultati. Misurare tempi a freddo e a caldo, RAM con entrambi i motori attivi e spazio occupato da modello, pacchetto e collezione. Impostare `SEMANTIC_ENABLED=1` nell'ambiente dell'app e riavviarla per mostrare la voce nel selettore.
5. Per ripristinare il ranking precedente usare l'API Qdrant `POST /collections/aliases` con una singola transazione contenente `delete_alias` per l'alias attivo e `create_alias` sul nome di collezione precedente restituito dall'import. Per nascondere la voce nel selettore impostare `SEMANTIC_ENABLED=0` e riavviare l'app.

La verifica di portabilità usa lo stesso pacchetto su PC e Linux. Confrontare ID e punteggi su query fisse. Per una rigenerazione indipendente conservare i due report, confrontare le top 10 e ispezionare scambi tra documenti con punteggi quasi uguali.

#### Corpus completo e trasferimento verificato

Per indicizzare tutti i documenti validi del corpus usato dal lettore locale:

~~~sh
uv run --locked wikinews-ir semantic generate --corpus data/processed/m2-v1 --package data/processed/semantic-qwen3-06b-full
uv run --locked wikinews-ir semantic import --check-archive --package data/processed/semantic-qwen3-06b-full
uv run --locked wikinews-ir semantic verify --check-archive --package data/processed/semantic-qwen3-06b-full
~~~

Il pacchetto completo di questo snapshot deve contenere 11.032 documenti. Per trasferirlo, usare dal PC `uv run python scripts/transfer_semantic.py data/processed/semantic-qwen3-06b-full --host UTENTE@VPS --key PERCORSO_CHIAVE`. Il comando verifica i batch prima della copia, quindi controlla i checksum sulla VPS e pubblica la directory verificata sotto `/opt/newsfinder/imports`. L'ultima riga indica il percorso da usare per l'importazione sul server. Questa operazione trasferisce i vettori e i metadati e lascia i servizi di produzione in esecuzione con la configurazione corrente.


Per riprendere il build completo, verificarlo, attivarlo in locale e trasferirlo alla VPS configurata in questo progetto, eseguire dalla root `uv run --locked python scripts/complete-semantic-build.py`. Il pacchetto usa Qwen3 Embedding 0.6B con 1.024 dimensioni. Il budget di 256 token include il token finale EOS.

## Collaudo

Il 19 novembre 2026 la demo locale ha superato l’installazione da clone pulito e la prova browser su loopback. Il download storico rispondeva HTTP 403; il dump del corso, verificato tramite checksum, ha permesso la build offline. Dopo il riavvio gli indici conservavano gli stessi UUID. Sul sito pubblico il verbale documenta HTTP 200 per ricerca e annotazione; la conferma dei controlli individuali e del ripristino della copia PC resta aperta. Annotare qui ambiente, data, esito e problemi della futura prova in aula. [Copione](consegna/demo.md)
