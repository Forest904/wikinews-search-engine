# M6-B · Esperimenti sul benchmark di produzione

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

## Riproduzione e verifica

Dalla radice del repository, con gli artefatti M5-D sulla macchina, le tre fasi sono:

```powershell
uv run --locked wikinews-ir benchmark m6b development
uv run --locked wikinews-ir benchmark m6b freeze
uv run --locked wikinews-ir benchmark m6b final
```

L’esecuzione iniziale delle varianti richiede gli indici Elasticsearch locali identificati nel manifest M5. I successivi accessi riusano le run salvate. Il comando finale su un registro completato verifica e restituisce la ricevuta. Conservare insieme registro, congelamento e directory dei risultati. Gli orari del registro sono UTC.

In `experiments/reports/m6b-production-1.1`, le directory `development` e `final` contengono il report canonico con metriche per query, denominatori, copertura, grafico, matrice e disaccordi. La sottodirectory `analysis` contiene differenze appaiate, estremi con ranghi e gradi, risultati per refuso, ordinamenti e medie per scenario. `variant-runs` contiene le due run TREC. Il protocollo include gli hash del codice e della configurazione effettivamente usati. Per verificare l’indice dell’esecuzione originale:

```powershell
$index = Get-Content benchmarks/v1/manifests/m6b-production-1.1.json -Raw | ConvertFrom-Json
foreach ($entry in $index.sha256.psobject.Properties) {
    if ((Get-FileHash -LiteralPath $entry.Name -ErrorAction Stop).Hash -ne $entry.Value) {
        throw "Checksum diverso per $($entry.Name)"
    }
}
```
