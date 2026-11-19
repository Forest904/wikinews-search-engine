# ADR 0004 — Baseline M3 sul corpus reale

Data: 2026-11-16. Stato: implementato e verificato localmente.

## Decisione

E0 interroga `wikinews_standard_v1`, E1 `wikinews_italian_v1`. Entrambi usano
lo stesso corpus M2, BM25 k1=1.2/b=0.75, `multi_match` best_fields con OR e
campi title/body di uguale peso. Cambia soltanto l'analyzer standard/italian.
Il default E0 non costituisce una selezione sperimentale del modello migliore.

Le definizioni in `configs/` sono replicate nelle risorse del pacchetto per
funzionare anche da wheel/container; un test ne impone l'identità. Una modifica
agli analyzer richiede una nuova versione di indice, ai profili una nuova versione
di profilo. In M3 erano attivi E0 ed E1. M4 ha aggiunto E2–E4 secondo [ADR 0005](0005-advanced-retrieval.md). M6-B ha selezionato E1 sul development. Il default della UI rimane E0.

La costruzione valida tutti gli artefatti M2 e ogni record prima di mutare gli
indici. Bulk streaming, ID stabili, retry limitati e verifica dell'intero `_source`
impediscono di scambiare un conteggio corretto per un corpus corretto.
Gli indici completi vengono bloccati in scrittura. I manifest di costruzione sono
separati da quelli M2 e includono configurazioni, UUID, checksum, versioni e tempi.
Il riuso verifica anche i contenuti; `--rebuild` ricrea solo i due indici fisici
configurati, dopo il preflight. Non è un rollout senza interruzioni: durante la
ricostruzione la ricerca può restituire 404/503. Nessun alias o wildcard è ammesso
come destinazione del comando di costruzione.

## Contratti e compatibilità

Il passaggio M1→M3 è intenzionalmente incompatibile: `bm25` e `limit` vengono
sostituiti da `E0`/`E1` e `page_size`; `page` parte da 1. Query 1–250 caratteri,
page_size 1–100, finestra massima 10.000 risultati. L'API rifiuta `limit` con 422.
I rank sono assoluti. Il sort è score decrescente, document_id keyword crescente
(ordine lessicografico, non numerico). I totali sono esatti; `elapsed_ms` rimane
il tempo `took` del backend, non la latenza HTTP.

API, UI ed export usano lo stesso RetrievalEngine. Metadati di corpus, indice e
profilo accompagnano le risposte. Il dettaglio legge il profilo selezionato e
mantiene il contesto della ricerca nel link di ritorno. `/api/health` controlla
la connessione, `/api/ready` anche i due indici e il corpus condiviso.
Le fixture vivono in indici demo separati e non vengono mescolate al corpus reale.

L'export accetta query JSONL con query_id univoco e query, produce due TREC e un
manifest, senza leggere qrels. Output occupati vengono rifiutati; errori non
pubblicano directory finali parziali. Top-k 1–1.000, default 100. Score originali
conservati: un futuro lettore TREC deve rispettare il rank/tiebreak dichiarato,
perché alcune librerie riordinano autonomamente i documenti a pari score.

## Evidenze e conseguenze

Vedere [report M3](../m3-validation.md) per ricostruzioni, hash, misure e review.
Il wheel include tutte e quattro le configurazioni runtime. La CI usa solo
fixture temporanee, mentre il collaudo completo del corpus è locale.

Restano limiti di ingestion già nel corpus M2: riquadri di navigazione degli
speciali possono entrare nel body e nello snippet. Una correzione richiederà una
nuova versione del corpus e degli indici. Nessun tuning o giudizio di superiorità
E0/E1 è derivato dalle query smoke. CI remota da verificare dopo il push.
