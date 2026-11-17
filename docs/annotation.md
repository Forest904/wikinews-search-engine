# Annotazione collaborativa — M5-B

M5-C aggiunge timer, blocchi di calibrazione con tre validatori e discussione
separata dall'adjudication: [guida pilot](m5c-pilot.md). La migrazione SQLite v2
preserva i dati v1; effettuare backup prima dell'aggiornamento.

La postazione `/annotate` e la pagina `/coordinate` lavorano su pacchetti M5-A
importati in SQLite. Ricerca, Elasticsearch, Web e LLM non sono necessari per
annotare. M5-B è collaudata localmente su fixture; accesso online e raccolta reale
appartengono a M7-A e M5-C/D. Evidenze: [report M5-B](m5b-validation.md).

## Avvio locale e account

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

### Avvio Docker

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

## Lavoro del coordinatore

La pagina è divisa in **Panoramica**, **Assegnazioni**, **Revisioni** ed
**Esportazione**, raggiungibili anche tramite il frammento dell'URL. Cambiare
sezione conserva i moduli in memoria. **Blocchi preparati** è richiudibile sotto
il modulo di preparazione: si apre dopo aver creato un blocco, evidenziando la
nuova bozza. La discussione pilot non è più esposta nella UI; dati storici e API
restano disponibili per gli strumenti del protocollo M5-C.

1. Scegliere pacchetto e topic, valutatore principale e secondo valutatore facoltativo.
2. Specificare il numero di documenti in doppio e un seed. Il principale riceve
   tutte le coppie del topic; il secondo un sottoinsieme deterministico. Anche
   l'ordine per utente è deterministico, indipendente dal ranking del retrieval.
3. Preparare il blocco, leggere il riepilogo e attivarlo. La bozza non distribuisce
   attività; l'attivazione è atomica e congela le assegnazioni del topic nel pacchetto.
4. Seguire completati, astensioni, rinvii e revisioni. La dashboard mostra conteggi,
   non gradi o motivazioni individuali.
5. Assegnare i casi pendenti a un utente non coinvolto nell'annotazione della
   coppia. Nelle doppie annotazioni questo è il terzo valutatore.

Le quote usate nel demo sono esempi tecnici. Budget e campionamento reali restano
decisioni di M5-C. I blocchi attivi non si riassegnano né si ampliano dopo aver
osservato giudizi; errori nel disegno richiedono un nuovo pacchetto di raccolta.

## Lavoro del valutatore

La pagina presenta il bisogno informativo in una fascia superiore orizzontale,
con criteri e rubrica chiusi di default e un piccolo badge timer inline accanto. Il timer parte chiuso: il suo
riepilogo indica sempre stato e fase; richiuderlo non mette in pausa il conteggio.
Sotto, il documento occupa il 75% dello spazio desktop e il giudizio il 25%,
che segue lo scorrimento su desktop. Su mobile le sezioni sono impilate, con
collegamenti rapidi Criteri / Documento / Giudizio. I criteri tornano chiusi al
cambio di topic.

- Leggere bisogno informativo, inclusioni, esclusioni e rubrica specifica.
- Usare la ricerca facoltativa e le frecce per navigare tra le occorrenze: non suggerisce gradi.
- Selezionare passaggi nel corpo e premere **Cita il passaggio** vicino al testo
  oppure **Aggiungi citazione** nel modulo. Le citazioni
  conservano offset Unicode e sono verificate sul testo congelato anche al salvataggio.
- Scegliere `0`, `1` o `2`, aggiungere una motivazione. Ogni grado richiede almeno
  una citazione. Le scorciatoie numeriche funzionano fuori dai campi di inserimento.
- **Salva** mantiene l'attività; **Salva e continua** passa alla successiva solo
  dopo conferma del server. La causale rapida aggiunge testo modificabile alla motivazione.
- **Astieniti** richiede una motivazione e registra `needs_review`, senza grado.
  **Riprendi dopo** conserva motivazione e citazioni come bozza `deferred`, senza grado.
  Rinviare non equivale ad assegnare zero né a completare l'annotazione.
- **Modifica ultimo giudizio** riapre il salvataggio più recente. La cronologia
  conserva tutte le proprie revisioni. Dopo un conflitto, ricaricare il giudizio
  salvato e riconciliare la modifica: nessuna sovrascrittura silenziosa.

Il riepilogo personale distingue giudizi, astensioni e rinvii. L'ultima attività
si ricorda nella sessione browser; i contenuti salvati sono nel database e possono
essere ripresi anche da un altro computer. Le modifiche non ancora inviate restano
solo nel form: prima di chiudere usare **Riprendi dopo**. La pagina avvisa quando
si abbandona un modulo modificato e lo conserva in caso di errore di salvataggio.

## Finalizzazione e revisione

Una coppia viene finalizzata automaticamente solo quando tutte le annotazioni
previste sono graduate e concordano, incluso il caso con un solo annotatore.
La finale è un record separato; nessun giudizio iniziale viene sovrascritto.

Disaccordi e astensioni aprono una revisione dopo il completamento delle attività
previste. Un rinvio mantiene la coppia in attesa. Solo il revisore assegnato vede
gli originali nella scheda **Revisioni assegnate**; il ruolo di coordinatore da
solo non li rende accessibili in questa scheda. Il revisore può concludere con
un grado motivato e citato oppure un'astensione finale.

Ogni modifica a un originale invalida la finale corrente nella stessa transazione
e riesegue il consolidamento. Una revisione aperta su originali superati riceve
un conflitto e deve essere ricaricata. Finali superate e originali restano nello
storico; le richieste ripetute con la stessa chiave non creano doppioni.

## Export e separazione del test

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

## Persistenza, backup e aggiornamenti

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

## Verifiche ripetibili

```powershell
uv run --locked ruff check .
uv run --locked pytest tests/unit/test_annotation.py -q
uv run --locked playwright install chromium
$env:RUN_ANNOTATION_E2E = "1"
uv run --locked pytest tests/browser -q
Remove-Item Env:RUN_ANNOTATION_E2E
```

Il job CI `annotation-browser` esegue il collaudo senza avviare Elasticsearch.
Screenshot e archivio gold sintetico sono in `output/playwright/annotation/`.
La pubblicazione online, il backup remoto e il collaudo da computer distinti
restano il gate M7-A.

`/api/health` continua a descrivere lo stato del servizio di ricerca: una sua
risposta 503 per Elasticsearch spento non impedisce l'uso dell'area valutatori.
