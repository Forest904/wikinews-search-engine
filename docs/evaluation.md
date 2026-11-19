# Valutazione e risultati

## Identità e formati

I modelli sono in `evaluation/contracts.py`. Topic e giudizi usano `query_id`,
`document_id`, `revision_id` come stringhe; i documenti vengono da M2, senza nuovo
cleaning. Il benchmark conserva hash del corpo, identità del corpus, rubrica e
versione del protocollo. `event_family` non può attraversare calibration/development/test.
Le varianti sono proprietà del topic, non nuovi topic indipendenti.

Topic: query breve (unico input al retrieval), information need, narrative, rubrica
0/1/2, inclusioni/esclusioni, tipo, tema, periodo, famiglia, split e varianti.
La data editoriale del documento non sostituisce la data dell'evento.

Giudizi: grado 0/1/2 oppure `needs_review` con `grade: null`, motivazione ed evidenze
del `body`. Le evidenze usano offset Unicode, estremità finale esclusa. Per una
citazione univoca gli offset possono essere omessi e vengono calcolati durante
la validazione. Una citazione ripetuta richiede disambiguazione esplicita.

Gli artefatti sono directory nuove con `manifest.json`; le scritture passano da
staging e non sovrascrivono output esistenti. I file dati hanno serializzazione
deterministica; timestamp di esecuzione sono separati e non sono attesi identici
fra esecuzioni. I checksum rilevano modifiche accidentali: non sono firme digitali.

## Topic e riconciliazione

`benchmarks/topics/calibration-draft.jsonl` contiene quattro bozze adattate dal pilot
esterno, senza etichette. Non sono i 40 topic definitivi e non vanno spostate nel test
dopo la calibrazione. Le 48 coppie esterne sono diagnostiche, non un pool E0–E4.

```powershell
uv run --locked wikinews-ir benchmark validate --topics benchmarks/topics/calibration-draft.jsonl --protocol configs/evaluation/protocol.yaml
uv run --locked wikinews-ir benchmark reconcile-pilot --pilot "C:\percorso\evaluation\pilot" --corpus data/processed/m2-v1 --output experiments/reports/m5a-reconciliation-new
uv run --locked wikinews-ir benchmark queries --topics benchmarks/topics/calibration-draft.jsonl --protocol configs/evaluation/protocol.yaml --output experiments/runs/m5-queries
```

La riconciliazione legge soltanto topic, candidati e documenti esterni: non importa
gli script né le proposte. Produce report per coppia, hash di provenienza, topic,
testi M2 e coppie con revisioni corrispondenti. ID assenti o revisioni diverse sono
segnalati e non sostituiti automaticamente. Anche con la stessa revisione il testo
pulito può differire: le vecchie citazioni non sono trasferite.

## Run, pool e selezione

L'export locale esistente rimane invariato. I comandi seguenti descrivono una futura
esecuzione reale; **non sono stati eseguiti sulle quattro query in M5-A**.

```powershell
uv run --locked wikinews-ir runs export --queries experiments/runs/m5-queries/queries.jsonl --output experiments/runs/m5-local --top-k 100
uv run --locked wikinews-ir benchmark external-run --topics benchmarks/topics/calibration-draft.jsonl --corpus data/processed/m2-v1 --output experiments/runs/m5-external --live --top-k 100 --user-agent "WikinewsIR/0.1 (contatto reale del responsabile)"
uv run --locked wikinews-ir benchmark pool --topics benchmarks/topics/calibration-draft.jsonl --corpus data/processed/m2-v1 --runs experiments/runs/m5-local experiments/runs/m5-external --output experiments/runs/m5-pool
uv run --locked wikinews-ir benchmark select --pool experiments/runs/m5-pool --output experiments/runs/m5-selection
```

Il parametro 100 è un esempio tecnico, non una decisione del pilot. Wikimedia usa
la ricerca attuale in namespace 0, non ricostruisce il ranking del 2025. Le richieste
sono seriali con timeout e massimo tre tentativi per errori transitori. Errori,
warning o paginazione incompleta impediscono la pubblicazione dell'artefatto completo.

`external-run --replay <archive.json>` sostituisce `--live` e non chiama la rete.
Il file archivio contiene endpoint, top_k e pagine con query_id, parametri,
captured_at e risposta originale. Il replay verifica query, continuation e profondità.
I risultati sono mappati per page ID; fuori corpus sono registrati, non negativi.
La proiezione TREC sul corpus rinumera i rank e usa score convenzionale `1/rank`;
`results.jsonl` conserva le posizioni originali, anche per i risultati fuori corpus.
Fonti tecniche: [Search](https://www.mediawiki.org/wiki/API:Search) e
[Etiquette](https://www.mediawiki.org/wiki/API:Etiquette) di MediaWiki.

In caso di fallimento live dopo tentativi HTTP viene conservato un artefatto
`external-run-failed` con diagnostica e risposte ricevute, mai utilizzabile come run
completa. Per riprovare scegliere una nuova directory di output.

Il pool verifica checksum, identità del corpus, query e conteggi delle run e conserva
tutte le provenienze. Non mescola due versioni della stessa run con ID coincidenti.
La selezione predefinita è l'unione completa. Con `--quotas quote.json --seed 42`,
il JSON deve specificare ogni run, per esempio `{"E0-v1": 10, "E1-v1": 10}` per
un pool con quelle sole due run. Le quote sono **per topic e run**; campionamento
senza rimpiazzo, deduplicazione successiva, nessun riempimento implicito. Il report
registra quote richieste/disponibili/estratte e numero finale di coppie distinte.

## Gold e qrels

`export-qrels --source gold --judgments <human.jsonl>` accetta giudizi umani e
decisioni finali nello stesso file. Ogni finale deve riferire tutti i giudizi
originali della coppia tramite `origin_judgment_ids`; gli originali non sono
sovrascritti. L'adjudication è gestita dalla UI M5-B. Giudizi senza finale,
finali duplicati, fonti mescolate o riferimenti mancanti impediscono l'export.

I qrels usano quattro colonne TREC: query, `0`, documento, grado. Astensioni
finalizzate sono escluse e contate; coppie assenti restano unjudged. Gold e silver
rimangono file e manifest distinti. Non esiste conversione automatica silver→gold.

L'export M5-B include nei qrels solo le coppie consolidate e allega separatamente
la cronologia completa; `judgments.jsonl` contiene gli originali correnti di tali
coppie e le rispettive finali. Singoli/accordi vengono consolidati automaticamente,
con provenienza esplicita; i disaccordi richiedono il revisore indipendente.
Gli export sono separati per split e il test richiede rilascio esplicito registrato.

## Raccolta

Nel pilot 22 giudizi silver su 24 coincidevano con il riferimento di calibrazione. Il pacchetto di produzione ha separato development e test prima della raccolta. I valutatori hanno prodotto 190 giudizi gold, il percorso silver 982; 190 coppie sono condivise. Conservare la provenienza dei giudizi e trattare le coppie prive di valutazione come tali. I file versionati identificano split, pool e pacchetti. [Manifest](../benchmarks/v1/manifests/)

## Risultati sperimentali

Il 19 novembre 2026 E1 (BM25 con analyzer italiano) è stato selezionato sui 24 topic development. La regola congelata massimizza nDCG@10 gold sulle query canoniche, poi P@5 e infine preferisce il primo profilo nell’ordine E0–E4. Il registro contiene un avvio e un completamento del test sui 16 topic. Lo snapshot comprende 11.032 documenti e la profondità disponibile è 100. Wikimedia usa la proiezione sul corpus della run archiviata in M5. [Indice degli artefatti](../benchmarks/v1/manifests/m6b-production-1.1.json)

| Sistema | Dev nDCG@10 | Dev P@5 | Test nDCG@10 | Test P@5 | Test MRR@10 |
|---|---:|---:|---:|---:|---:|
| E0 · standard | 0,5785 | 0,2333 | 0,5963 | 0,2250 | 0,7500 |
| **E1 · italiano** | **0,6659** | **0,2833** | **0,6558** | **0,2500** | 0,6250 |
| E2 · boost titolo | 0,5771 | 0,2333 | 0,5022 | 0,1625 | 0,3333 |
| E3 · fuzzy | 0,5653 | 0,2250 | 0,5022 | 0,1625 | 0,3333 |
| E4 · frase | 0,5771 | 0,2333 | 0,5022 | 0,1625 | 0,3333 |
| Wikimedia | 0,5212 | 0,2417 | 0,5414 | 0,1750 | 0,7500 |

Le metriche primarie comprendono tutti i topic di ciascuno split. MRR considera i quattro topic test di tipo evento. P@5 e MRR usano la soglia di rilevanza 1. E1 migliora in media su E0 nelle due metriche primarie, ma il primo risultato rilevante sui topic evento favorisce E0 e Wikimedia. Le differenze sono descrittive. Il campione e il pooling limitano la generalizzabilità.

## Ablation ed errori

- **Analyzer.** Nel test Q37, sugli incidenti ferroviari in Giappone, E1 porta due articoli di grado 2 (1374 e 2273) ai primi due posti. E0 presenta un articolo di grado 1 al secondo posto e nove risultati senza giudizio in top 10. Il guadagno nDCG è 0,6994. Su Q09 il documento 4230 di grado 2 scende dal primo al secondo posto e nDCG cala di 0,3691.
- **Titolo.** Su Q09 E2 spinge 4230 fuori dai primi dieci e perde altri 0,6309 rispetto a E1. Su Q29, relativo a Michael Schumacher, conserva il primo risultato di grado 2 e porta un secondo articolo dello stesso grado (5090) all’ottavo posto, con un guadagno di 0,1934.
- **Refusi.** Ciascun topic ha una variante congelata. Sul development la perturbazione riduce nDCG di 0,1138 per E2 e di 0,0827 per E3. Sul test le perdite sono 0,1434 e 0,1401. Il vantaggio fuzzy nella tenuta ai refusi scende quindi da circa 0,031 a 0,003. Le perdite test di P@5 sono 0,0500 e 0,0375. Sulle query canoniche E3 può anche peggiorare il ranking. Nella query development sui rover marziani l’articolo 21965 di grado 1 esce dalla top 10 e 17915 passa dalla quinta alla sesta posizione.
- **Vincoli multipli.** Le sei query development e le quattro test di questo tipo attivano la clausola di frase opzionale di E4. Nessuna contiene una frase esplicitamente virgolettata. Tutti e dieci i ranking esportati coincidono con E2, con differenze nulle per entrambe le metriche primarie. L’esperimento non misura il comportamento delle frasi obbligatorie.

## Copertura e sensibilità

Per E1 il gold copre 43/120 risultati development a 5 e 68/240 a 10. Sul test copre 31/80 a 5 e 43/160 a 10. Nella valutazione primaria i risultati senza giudizio conservano il rank con guadagno nullo. Rimuovendoli dai primi 100 prima del cutoff, nDCG test di E1 passa da 0,6558 a 0,7842. E1 resta primo, mentre Wikimedia scende dietro E2–E4 nel ranking condensato. La differenza mostra quanto la posizione dei documenti senza giudizio pesi sul confronto. Il recall assoluto rimane sconosciuto.

## Gold e silver

| Split | Coppie condivise | Macro-F1 | Kappa lineare | Silver inferiore / superiore al gold |
|---|---:|---:|---:|---:|
| Development | 116 | 0,6810 | 0,7964 | 11 / 9 |
| Test | 74 | 0,8357 | 0,8803 | 6 / 0 |

Sulle coppie condivise E1 resta primo per nDCG in entrambi gli split. Nel development cambiano verso 6 confronti su 15 fra sistemi. Nel test tutti i 15 confronti nDCG conservano ordine o parità, mentre in P@5 cambiano tre relazioni di parità. Sul test i sei disaccordi assegnano tutti un grado silver inferiore. Questo andamento riguarda le 74 coppie osservate. Sul silver completo (595 coppie development e 387 test), E1 ottiene nDCG 0,5739 e 0,5939. I due insiemi hanno copertura diversa.



## Risultati della consegna

Il commit sperimentale è `1c6e51d`. Per ricostruire la tabella principale leggere i due file `canonical/summary.tsv` sotto `experiments/reports/m6b-production-1.1/{development,final}`, filtrare source=gold e arrotondare mean a quattro decimali. I denominatori sono nella colonna topics. La release distribuisce i file del manifest M6-B insieme alle sei run canoniche e ai qrels gold/silver in un [archivio ZIP](https://github.com/Forest904/wikinews-search-engine/releases/download/v1.0.0/risultati-m6b.zip) da estrarre nella radice del clone. Verificarli con il comando del report prima di usarli. Gli input privati di raccolta rimangono presso il coordinatore. [Risultati sperimentali](#risultati-sperimentali)

Da PowerShell, nella radice di un clone della release, salvare lo ZIP scaricato nella directory superiore ed eseguire:

```powershell
$zip = "../risultati-m6b.zip"
if ((Get-FileHash $zip).Hash -ne "c8b16318b31d145883b275a54a2d6e93fbe979f6c39fa9643fd829846d2fa967") { throw "ZIP diverso dalla release" }
Expand-Archive -LiteralPath $zip -DestinationPath . -Force
Import-Csv experiments/reports/m6b-production-1.1/final/canonical/summary.tsv -Delimiter ([char]9) |
    Where-Object source -eq gold | Format-Table run,metric,mean,topics
```

L’estrazione ripristina anche i byte originali del manifest M5-D per la verifica SHA-256 su sistemi con conversione automatica dei fine riga. Per confrontare entrambe le partizioni, ripetere la lettura della tabella sostituendo `final` con `development`.

## Prestazioni

La misura M4-P comprende due sessioni e 400 richieste senza errori. L’ordine fisso dei profili e il carico locale limitano il confronto. Distinguere latenza del client, tempo interno di Elasticsearch e capacità della Web UI. [Misure storiche per profilo](https://github.com/Forest904/wikinews-search-engine/blob/11577cdc898add969a5ab3ce9551f8cf8bdec511/docs/m4p-validation.md)

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

## Provenienza storica

I protocolli congelati citano il PRD e i nomi dei verbali originali. Per interpretarli consultare il [PRD della revisione di riferimento](https://github.com/Forest904/wikinews-search-engine/blob/11577cdc898add969a5ab3ce9551f8cf8bdec511/docs/prd.md) e il [registro delle decisioni](https://github.com/Forest904/wikinews-search-engine/tree/11577cdc898add969a5ab3ce9551f8cf8bdec511/docs/decisions).
