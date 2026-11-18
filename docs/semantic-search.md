# Ricerca semantica

La modalità **Ricerca semantica** ordina per similarità coseno tra la query e titolo/apertura. Il profilo HTTP è `semantic`. Il lettore continua ad aprire la revisione dell'archivio Elasticsearch. Il testo mostrato al lettore e gli offset delle annotazioni provengono dal corpus originale.

## Preparazione e prova locale

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

## Valutazione

Con i due pacchetti importati e il profilo italiano Elasticsearch costruito sul medesimo corpus:

~~~sh
uv run python scripts/benchmark_semantic.py --queries benchmarks/topics/calibration-draft.jsonl --qrels experiments/runs/pilot-qrels-silver-001/qrels_silver.tsv --natural data/processed/semantic-qwen3-06b-natural --stem data/processed/semantic-qwen3-06b-stem --output experiments/reports/semantic-qwen3-06b.json
~~~

Il report limita i candidati E1 agli stessi articoli presenti in Qdrant e conserva le statistiche lessicali del corpus E1. Riporta nDCG@10, numero di risultati giudicati, ID da revisionare e tempi per query. I giudizi silver sono stime. Le query senza documenti rilevanti giudicati nel campione hanno nDCG indefinito. La variante indicizzata richiede a Qdrant la normale ricerca approssimata e misura la sovrapposizione con la ricerca esatta. Su collezioni piccole Qdrant può scegliere una scansione completa. Il profilo pubblico usa per default la ricerca esatta del pilota. Per usare la ricerca indicizzata impostare `SEMANTIC_EXACT=0`.

### Esito della calibrazione locale

Il confronto del 18 novembre 2026 usa i 24 articoli selezionati e le quattro query di calibrazione, con giudizi silver. La ricerca avviene sugli stessi candidati per tutti i profili.

| Profilo | nDCG@10 medio | Risultati giudicati nei primi 10 |
| --- | ---: | ---: |
| Elasticsearch E1 | 0,952 | 23 su 35 |
| Qwen2.5 3B su testo naturale | 0,349 | 13 su 40 |
| Qwen2.5 3B con stemming | 0,322 | 13 su 40 |

Nel precedente esperimento con Qwen2.5 3B, per la query sul terremoto in Abruzzo il profilo naturale ha collocato al primo posto la notizia della morte di Sergio Endrigo. Il testo naturale rimane il profilo semantico selezionabile per il pilota. Elasticsearch resta il motore predefinito. Con il contesto impostato a 2.048 token, Ollama ha riportato un ingombro locale di 2,0 GB per il modello.

## Attivazione e server

### Query elaborate dal PC Windows

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

### Corpus completo e trasferimento verificato

Per indicizzare tutti i documenti validi del corpus usato dal lettore locale:

~~~sh
uv run --locked wikinews-ir semantic generate --corpus data/processed/m2-v1 --package data/processed/semantic-qwen3-06b-full
uv run --locked wikinews-ir semantic import --check-archive --package data/processed/semantic-qwen3-06b-full
uv run --locked wikinews-ir semantic verify --check-archive --package data/processed/semantic-qwen3-06b-full
~~~

Il pacchetto completo di questo snapshot deve contenere 11.032 documenti. Per trasferirlo, usare dal PC `uv run python scripts/transfer_semantic.py data/processed/semantic-qwen3-06b-full --host UTENTE@VPS --key PERCORSO_CHIAVE`. Il comando verifica i batch prima della copia, quindi controlla i checksum sulla VPS e pubblica la directory verificata sotto `/opt/newsfinder/imports`. L'ultima riga indica il percorso da usare per l'importazione sul server. Questa operazione trasferisce i vettori e i metadati e lascia i servizi di produzione in esecuzione con la configurazione corrente.


Per riprendere il build completo, verificarlo, attivarlo in locale e trasferirlo alla VPS configurata in questo progetto, eseguire dalla root `uv run --locked python scripts/complete-semantic-build.py`. Il pacchetto usa Qwen3 Embedding 0.6B con 1.024 dimensioni. Il budget di 256 token include il token finale EOS.
