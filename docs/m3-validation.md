# Verifica locale M3 — 16 novembre 2026

## Corpus, ambiente e riproducibilità

Entrambi gli indici contengono **11.032 documenti**, con verifica dell'intero
contenuto `_source` rispetto al processed M2. Nessuna modifica al corpus.

- SHA-256 `articles.ndjson`: `b85295e118431f71b06c56b04a27ca76010f90004eb45d29256ec8bca9443b45`.
- Windows, AMD Ryzen AI 7 350, circa 32 GiB RAM host; Docker Desktop, heap ES 1 GiB.
- Python 3.12.2, Elasticsearch 9.5.6, client 9.5.1. Working tree modificato:
  i manifest registrano il commit di base e `git_dirty=true`, non un commit finale.
- Prima costruzione: E0 **7,51 s**, E1 **6,07 s**; ricostruzione: **5,54 s / 5,87 s**.
  Durate per indice comprendenti bulk, refresh e verifica; preflight corpus escluso.
- Riutilizzo verificato senza riscrittura; UUID cambiati dopo rebuild.
- Le dieci query in `configs/smoke/queries.jsonl`, top-100, producono file identici
  su due run consecutive e dopo ricostruzione completa.

| Artefatto | SHA-256 identico nelle tre run |
|---|---|
| E0.trec | `229f89606b4311e1aff548f384dbc97949af65cc0b90a5157fccadffb304b0ad` |
| E1.trec | `05e68e06d6546155a09c50a17fd290f0016705c906c5a6a7279b9cbf7bdba39b` |

Artefatti locali ignorati da Git: `output/m3-validation/report.json`,
`output/m3-validation/run-{first,repeat,rebuilt}/`, manifest di costruzione in
`experiments/reports/index-build/`. Per ripetere usare una directory nuova:

```bash
uv run --locked python scripts/verify_m3.py --output output/m3-check --rebuild
```

## Tempi orientativi

Dieci query, un passaggio di warmup, cinque ripetizioni: 50 misure per profilo,
page_size 10. Tempo wall-clock del RetrievalEngine, comprese verifica metadata,
chiamate ES e conversione dei risultati; non include HTTP FastAPI/rendering browser.

| Profilo | Mediana | p95, nearest rank |
|---|---:|---:|
| E0 | 19,50 ms | 22,70 ms |
| E1 | 18,02 ms | 22,25 ms |

Misure locali a cache calda, senza carico concorrente controllato: non sono SLA
né prova di superiorità prestazionale. `elapsed_ms` dell'API continua a riportare
solo `took` Elasticsearch e non va confuso con queste misure.

## Review qualitativa dei primi cinque risultati

Ispezionati titoli e testo iniziale delle prime cinque query per entrambi i profili
(50 posizioni, con documenti ripetuti). I corpi completi sono conservati nel report
locale per approfondimenti. Nessuna etichetta gold/silver viene prodotta.

| Query | Osservazione e classificazione |
|---|---|
| terremoto Abruzzo 2009 | Documenti 26038/26061/26053/26067 e 26045 contengono riquadri dello speciale prima della notizia: **residuo di ingestion**, dominante nello snippet. E0 include 43994 sul terremoto del 2016 che cita il 2009: **limite di ranking/ambiguità temporale**. |
| elezioni Italia | Risultati su diversi anni coerenti con una query ampia. In 4530/4491 rimane navigazione su articoli correlati: **ingestion**. La query non specifica anno o tipo di elezione: **ambiguità**. |
| Samantha Cristoforetti | 51079/51116 riguardano l'astronauta, 41015 la menziona incidentalmente; 35115/31812 parlano di Samantha Stosur: **matching OR e disambiguazione**, non perdita di testo in ingestion. Stessa top-5 nei due profili. |
| energia rinnovabile | E1 recupera anche forme plurali (12192/50982/23475). E0 include 39603 sull'elettricità in Crimea e 47144 sulla politica altoatesina: **matching parziale della query**. Non è una misura di miglioramento. |
| alluvione Genova | Entrambi mescolano alluvioni in altri luoghi e 46013 sul ponte Morandi: **mancata congiunzione tema/luogo** della baseline OR. Non si deduce che il documento desiderato sia assente dal corpus. |

I residui M2 restano espliciti: correggerli richiederà un nuovo corpus versionato e
nuove run. La review non cambia analyzer, boost o policy OR. Le query smoke non
costituiscono un benchmark e non giustificano conclusioni E1 > E0.

## Collaudo software

Esito finale locale: **119 test superati**, nessuno saltato con entrambi i flag
RUN_INTEGRATION/RUN_E2E attivi; Ruff superato e `git diff --check` senza errori.
Un warning preesistente di deprecazione Starlette/httpx, senza fallimenti.
Wheel costruito e reinstallato in ambiente separato: ricerca E1 eseguita con
successo e configurazioni runtime caricate dal pacchetto.

Test offline, integrazione autenticata ed E2E Chromium verificano schemi, errori,
checksum, bulk parziale, indici incompatibili, analyzer su forme flesse, tie-break,
paginazione, riuso, rebuild, export atomico e ripristino del contesto UI.
Il wheel contiene mapping e profili runtime. La CI resta su fixture sintetiche;
l'esito remoto è da verificare dopo il push.

Controllo browser sul corpus reale: E0/E1, pagina successiva, dettaglio e link
di ritorno; screenshot in `output/playwright/m3-real-page2.png`. La risorsa favicon
non è presente (404 cosmetico), senza effetto sulla ricerca.
