# Benchmark M5-A — preparazione offline e silver Codex

Il benchmark di produzione M5-C è congelato. Il pilot comprende 24 riferimenti di calibrazione e 24 giudizi silver. La raccolta di produzione appartiene a M5-D e la valutazione sperimentale a M6. [Risultati e manifest del congelamento](m5c-validation.md#congelamento-di-produzione-del-18-novembre-2026).

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

## Pacchetto comune e workspace Codex

```powershell
uv run --locked wikinews-ir benchmark packet --topics benchmarks/topics/calibration-draft.jsonl --protocol configs/evaluation/protocol.yaml --selection experiments/runs/m5-selection --corpus data/processed/m2-v1 --output experiments/runs/m5-packet
uv run --locked wikinews-ir benchmark silver prepare --packet experiments/runs/m5-packet --output output/codex-batch-001 --batch-id batch-001
```

Il pacchetto comune contiene topic, rubrica, testi completi e coppie, senza ranking,
provenienze del retrieval o altre etichette. `silver prepare` crea un workspace
autonomo con `PROMPT.md`, `README.md`, schema JSON, esempio sintetico e `validate.py`.
Il validatore richiede solo Python 3. Per un batch test il protocollo deve essere
`frozen`; il congelamento formale di prompt e selezione è responsabilità M5-C.

L'utente apre **solo il workspace del batch** in VS Code, avvia una chat nuova,
seleziona il modello e incolla il prompt. Non allega gold o report precedenti.
La separazione è organizzativa e dei dati forniti, **non una sandbox degli accessi**.
L'agente deve leggere solo i materiali del batch, trattare gli articoli come dati,
non usare Web o conoscenze esterne, salvare progressivamente e conservare gli output
precedenti prima di correggere i risultati. Nessun client API LLM è implementato.

Il validatore controlla formato, coppie, revisioni, hash, evidenze e completezza.
Gli errori tecnici non sono astensioni; un test superato non certifica la correttezza
semantica. `--allow-partial` serve solo per il lavoro in corso, non per importare.

```powershell
python output/codex-batch-001/validate.py --packet output/codex-batch-001 --judgments output/codex-batch-001/judgments.jsonl
uv run --locked wikinews-ir benchmark silver validate --packet output/codex-batch-001 --judgments output/codex-batch-001/judgments.jsonl
uv run --locked wikinews-ir benchmark silver import --packet output/codex-batch-001 --judgments output/codex-batch-001/judgments.jsonl --output experiments/runs/m5-silver-001 --operator revisore-1 --execution-id chat-001 --model unknown
uv run --locked wikinews-ir benchmark export-qrels --packet output/codex-batch-001 --judgments experiments/runs/m5-silver-001 --source silver --output experiments/runs/m5-qrels-silver
```

Il coordinatore usa il pacchetto originale verificato. `--model` è una dichiarazione
dell'operatore, non una verifica del modello: usare `unknown` se non noto. L'import
conserva output originale, versione normalizzata, report e metadati; `--prior-output`
accetta le precedenti versioni da archiviare. Non si dichiara la riproducibilità
esatta del ragionamento o delle etichette, ma quella degli artefatti e dei controlli.

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

## Verifica offline

### Riprodurre il report M6-A

Dalla radice del repository, in PowerShell, scegliere directory di destinazione nuove.

```powershell
$fixture = "output/m6a-fixture"
uv run --locked python scripts/m6a_fixture.py $fixture
uv run --locked wikinews-ir benchmark evaluate --topics "$fixture/topics.jsonl" --split development `
  --runs "$fixture/profile" "$fixture/external" --gold "$fixture/gold" --silver "$fixture/silver" `
  --fixture --output experiments/reports/m6a-fixture
```

Aprire `report.md` nella directory di output. Il comando accetta una o entrambe le fonti.
Per gli esperimenti M6-B usare i topic completi corrispondenti alle run, scegliere lo split,
passare le directory degli export consolidati e omettere `--fixture`. Per Wikimedia si valuta
la proiezione TREC sul corpus già prodotta dall’esportatore. Per tutti i profili vale il rank
esportato, anche quando più documenti hanno lo stesso score.

- `metrics.tsv` contiene una riga per run, fonte e query. nDCG@10 usa i gradi 0–2.
  P@5 divide sempre per 5 e considera rilevanti i gradi 1 e 2. MRR@10 considera gli stessi
  gradi sui soli topic di tipo `event-specific`.
- `summary.tsv` espone il denominatore di ogni macro-media. Un topic con almeno un grado
  valido entra nel calcolo anche se la run è vuota. Un topic senza gradi ha metriche N/D.
- `coverage.tsv` conta i risultati restituiti, giudicati e unjudged a 5 e 10. Le astensioni
  identificabili sono un sottoinsieme degli unjudged. Per i qrels M5-A è disponibile solo
  il totale delle astensioni dell’intero bundle. Il grafico divide il totale dei risultati
  giudicati per il totale restituito a ciascun cutoff. Una lista vuota ha copertura N/D.
- `confusion.tsv` usa righe gold e colonne silver. Il confronto considera l’intersezione
  delle coppie con grado in entrambe le fonti. La macro-F1 media le tre classi con F1 zero
  per una classe assente da entrambe. La kappa usa pesi lineari. `disagreements.tsv`
  elenca le singole coppie discordanti.
- `manifest.json` conserva checksum, fonti, split, versione di ir-measures, soglia,
  cutoff e denominatori. Gli export originali mantengono la provenienza dei giudizi.

### Controlli del repository

```powershell
uv run --locked ruff check .
uv run --locked pytest -m "not integration and not e2e"
```

I test includono una catena completa con corpus sintetico, run e HTTP simulati,
pacchetto Codex, esecuzione del validatore in Python isolato, import e qrels.
Le directory `experiments/runs`, `experiments/reports` e `output` restano ignorate;
topic adattati e contratti sono versionati. Nessuna dipendenza dal percorso Downloads.

## Risultati della consegna

Il commit sperimentale è `1c6e51d`. Per ricostruire la tabella principale leggere i due file `canonical/summary.tsv` sotto `experiments/reports/m6b-production-1.1/{development,final}`, filtrare source=gold e arrotondare mean a quattro decimali. I denominatori sono nella colonna topics. La release distribuisce i file del manifest M6-B insieme alle sei run canoniche e ai qrels gold/silver in un [archivio ZIP](https://github.com/Forest904/wikinews-search-engine/releases/download/v1.0.0/risultati-m6b.zip) da estrarre nella radice del clone. Verificarli con il comando del report prima di usarli. Gli input privati di raccolta rimangono presso il coordinatore. [Rapporto sperimentale](m6b-validation.md)

Da PowerShell, nella radice di un clone della release, salvare lo ZIP scaricato nella directory superiore ed eseguire:

```powershell
$zip = "../risultati-m6b.zip"
if ((Get-FileHash $zip).Hash -ne "c8b16318b31d145883b275a54a2d6e93fbe979f6c39fa9643fd829846d2fa967") { throw "ZIP diverso dalla release" }
Expand-Archive -LiteralPath $zip -DestinationPath . -Force
Import-Csv experiments/reports/m6b-production-1.1/final/canonical/summary.tsv -Delimiter ([char]9) |
    Where-Object source -eq gold | Format-Table run,metric,mean,topics
```

L’estrazione ripristina anche i byte originali del manifest M5-D per la verifica SHA-256 su sistemi con conversione automatica dei fine riga. Per confrontare entrambe le partizioni, ripetere la lettura della tabella sostituendo `final` con `development`.
