# Benchmark di NewsFinder

Eseguire dalla radice del repository. Il runner Python usa l'ambiente del progetto. Il generatore web richiede k6 sul PATH oppure il percorso del binario in `--k6`. La sonda browser usa Chromium installato con `uv run playwright install chromium`. Gli esempi usano PowerShell. Scegliere una directory nuova per ogni esecuzione.

## Motore e qualità

```powershell
uv run python scripts/performance/engine.py output/perf-engine
uv run --with matplotlib==3.11.2 python scripts/performance/report.py output/perf-quality --engine output/perf-engine --silver experiments/reports/m6b-production-1.1/final/silver
```

La configurazione predefinita misura E0–E4 sui topic di test e sui dieci casi prestazionali versionati. Ogni blocco ruota l'ordine dei profili e rimescola le query con un seed ripetibile. In ogni blocco il passaggio zero riscalda il servizio. Seguono tre passaggi misurati. I blocchi condividono il processo. Per stimare la dispersione fra avvii ripetere il comando in tre processi indipendenti. Conservare il manifest, i campioni JSONL e i percentili per blocco, profilo e classe. Per il primo avvio controllato riavviare soltanto i servizi della replica previsti dal protocollo e descrivere cache OS, modello e indice in `--cache-state`. Per confrontare query nuove e ripetute usare un solo profilo, `--sessions 1 --distinct-warmup` e confrontare i campioni first_pass e repeat a parità di query.

Aggiungere `--gold DIRECTORY_EXPORT` al report per ottenere risultati gold in una figura e un JSON dedicati. I bundle di giudizi si verificano mediante manifest. Conservare con la campagna l'identità del corpus sul quale sono stati raccolti. Il report usa le misure del progetto e calcola un bootstrap appaiato con 5.000 ricampionamenti dei topic rispetto a E1. MRR segue il criterio storico dei topic event-specific. La lista unjudged contiene coppie topic/documento da sottoporre a giudizio cieco. Per un nuovo test congelare i profili prima di raccogliere un nuovo insieme di topic e giudizi. Passare lo stesso file con `--topics` al runner e al report.

Per includere la ricerca semantica usare `--profiles E0 E1 E2 E3 E4 semantic --semantic-manifest PERCORSO` con la collezione completa attiva. Per il confronto su un sottoinsieme candidato comune, eseguire `scripts/benchmark_semantic.py --queries FILE --qrels FILE --natural DIR --stem DIR --output FILE`. Registra sovrapposizione dei top 10 fra ricerca esatta e indicizzata, copertura, tempo embedding e tempo Qdrant per conteggio e ricerca.

Nel confronto semantico `--stem` è facoltativo. Il report conserva lo stato Qdrant prima e dopo, inclusi punti e vettori indicizzati. Per una prova sull'approssimazione usare `--require-indexed` e controllare copertura dell'indice e stabilità dei segmenti. Con zero vettori indicizzati anche la ricerca con exact=false può fare una scansione esatta. La media nDCG storica di questo runner considera solo i topic con almeno un giudizio positivo nel sottoinsieme candidato; usare il report gold della suite per il confronto sullo split completo.

## Scalabilità e risorse

```powershell
uv run python scripts/performance/scale.py data/processed/m2-v1 output/perf-scale --build
```

Il seed determina campioni annidati al 10%, 50% e 100%. Senza flag vengono solo preparati i corpus. `--build` crea indici E1 con nomi univoci e conserva tempi di build verificata, documenti/s, dimensione Elasticsearch e tempi di query. I nomi degli indici creati sono in scale.json. `--embeddings` misura separatamente la generazione dei pacchetti, inclusi preparazione e scrittura. Richiede encoder e dump originale. Riutilizzare lo stesso hardware per tutti i campioni.

Avviare su ciascun host Docker il raccoglitore durante build o carico, indicando i nomi dei container su quell'host. Per ES includere `--es`. I record riportano timestamp, CPU, memoria, rete, block I/O e, con ES, heap, GC e thread pool search. Il massimo dei campioni di memoria è un picco osservato alla risoluzione scelta. Sincronizzare gli orologi del generatore e della replica. Controllare CPU e rete del generatore durante gli step.

```powershell
uv run python scripts/performance/resources.py output/resources.jsonl nome-app nome-es --es --seconds 900 --interval 5
```

## Web e browser

Usare una replica con worker, limiti memoria, indici, modello e topologia uguali al target. Registrare questi dati e la posizione del generatore in `--topology`. Ripetere la campagna verso l'applicazione e verso il proxy con gli stessi dati congelati. Le sessioni k6 verificano risultati, paginazione e identità dell'articolo. Chromium misura submit–risultato visibile, clic–testo leggibile, TTFB del lettore e stato cache della home.

```powershell
$base = 'http://127.0.0.1:8000'
uv run python scripts/performance/freeze.py $base output/oracle.json
$env:ORACLE = (Resolve-Path output/oracle.json).Path
uv run python scripts/performance/browser.py $base output/browser.jsonl --location locale
uv run python scripts/performance/campaign.py output/web-baseline --mode baseline --url $base --topology 'replica locale, un worker'
uv run python scripts/performance/campaign.py output/web-step --mode step --rate 2 --duration 5m --url $base --topology 'replica locale, un worker'
```

Generare l'oracolo sulla versione di riferimento e riusarlo per verificare esattamente gli ID su entrambe le versioni. Se una modifica intenzionale cambia il ranking, valutarla con i giudizi prima di congelare un nuovo oracolo. `QUERIES` accetta un array JSON di stringhe e deve corrispondere a `freeze.py --queries`. Scegliere query con almeno due pagine valide per lo scenario filter. Per provare più profili congelarli con `--profiles E1 semantic`.

| Mix | Percorso e configurazione |
| --- | --- |
| lexical | Home, ricerca E1, apertura del primo articolo. |
| mixed | Stesso percorso con quota semantica controllata da SEMANTIC_PERCENT. Ripetere con 0, 25, 50 e 100 e confrontare p95 E1 nel breakdown. |
| filter | Ricerca con intervallo anni, pagina 2 e controllo di duplicati, date e ID attesi. |
| archive | Archivio, cartella, articolo. FOLDERS contiene un array JSON di percorsi relativi di cartelle foglia popolati sulla replica, selezionati da cartelle piccole e grandi. |
| live | Ricerca e continuazione su replay. Per la fixture inclusa usare QUERIES uguale a ["Roma"]. |
| annotation | Su copia del DB usare DISPOSABLE=1, VUS e ACCOUNTS con percorso di un array JSON di account di prova con user_id e password. Predisporre un incarico attivo distinto per utente, uno per VU. Il runner salva un giudizio e rilegge versione, grado ed evidenza. Per account coordinatore legge anche la dashboard. |

Per la **capacità** usare `--mode capacity --rate 1 --max-rate 64 --p95-ms 800 --error-budget 0.01`. 800 ms e 1% sono esempi da sostituire con gli obiettivi concordati prima della campagna. Il runner raddoppia gli arrivi ogni cinque minuti, restringe l'intervallo fino a un arrivo/s e conferma i due estremi per 15 minuti ciascuno. Se raggiunge il limite configurato lo registra come massimo testato. Esaminare le serie temporali per code crescenti e i contatori del generatore prima di qualificare il risultato come capacità sostenibile. Ogni arrivo è un percorso, anche quando genera più richieste HTTP.

Per lo **spike** usare `--mode spike --rate N` con N uguale alla capacità misurata. Le fasi sono 5 minuti al 50%, 2 al 150% e 5 al 50%. Per la **durata** usare `--mode soak --rate N` per due ore al 70%. I tassi vengono arrotondati ad arrivi interi al secondo. Eseguire ogni mix separatamente, con directory distinte. Dimensionare VUS sul generatore e registrare le iterazioni scartate. I campioni HTTP sono inclusi nei file compressi k6.

## Dipendenze e recupero

Per il replay della fixture sintetica avviare la replica con l'entrypoint seguente. Per risposte registrate eseguire una sola volta `record_live.py output/live.json Roma` e specificare quel file in REPLAY_FILE. Conservare il suo hash. REPLAY_DELAY_MS controlla la latenza per chiamata upstream. Impostare 6000 per esercitare la scadenza del servizio. Riavviare il processo replay per svuotare la cache live prima di ogni confronto su un guasto.

```powershell
$env:REPLAY_FILE = 'configs/evaluation/live-replay.json'
uv run uvicorn scripts.performance.replay:app --port 8000
```

Per testare encoder o backend vettoriale, mantenere un carico mixed sulla replica dedicata e avviare sul relativo host `fault.py NOME_CONTAINER output/fault.jsonl --before 60 --seconds 30`. Il runner sospende quel container e lo riattiva dopo l'intervallo. Confrontare errori e p95 E1 e semantic prima, durante e dopo i timestamp registrati. Per il live lento affiancare un carico lexical separato e confrontare la sua latenza. Per il sito pubblico usare la sonda browser a basso volume.

## Lettura del report

Sul generatore si possono raccogliere CPU, memoria disponibile e contatori di rete con `uv run --with psutil python scripts/performance/resources.py output/generator.jsonl --host --seconds 900`. Sul server il file delle risorse va acquisito durante lo stesso intervallo del carico. Passare anche `--fault output/fault.jsonl` per evidenziare sospensione e ripristino sul grafico temporale.

```powershell
uv run --with matplotlib==3.11.2 python scripts/performance/report.py output/perf-web-report --web output/web-step/step.json.gz --resources output/resources.jsonl
```

Passare tutti gli step della campagna a `--web`. Il report produce la curva capacità–throughput utile–p95–errori, la serie temporale di recupero, i conteggi in finestre da 10 secondi e i percentili per endpoint e profilo. Le finestre parziali iniziale e finale restano nei campioni grezzi e sono escluse dalla curva. Il p99 viene pubblicato da 1.000 osservazioni per gruppo. Per dichiarare recupero confrontare finestre consecutive a carico equivalente con la distribuzione pre-guasto e verificare che il throughput utile torni al livello precedente. Per la decisione sul ranking affiancare quality-gold.png e i delta per topic ai p95 del motore.
