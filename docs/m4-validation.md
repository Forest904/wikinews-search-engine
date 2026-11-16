# Verifica locale M4 — 16 novembre 2026

## Corpus e riproducibilità

E0–E4 sono operativi sullo stesso corpus M2 di **11.032 articoli**. E1–E4 condividono
l'indice italiano; E0 usa quello standard. Build, riuso e rebuild verificano l'intero
contenuto, non soltanto il conteggio. Corpus e analyzer non sono cambiati.

Esecuzione completa:

```bash
uv run --locked python scripts/verify_m4.py --output output/m4-check --rebuild
```

Usare una directory nuova. Evidenze locali ignorate da Git in
`output/m4-validation-final/report.json`, `run-first/`, `run-repeat/`, `run-rebuilt/`
e `baseline-regression/`. Manifest con configurazioni/hash, UUID, query, versioni,
commit base e git_dirty=true. La validazione non identifica un commit finale.

Le otto query smoke M4 producono run top-100 identiche in due esecuzioni consecutive
e dopo rebuild. Le dieci query smoke M3 conservano esattamente gli hash E0/E1
registrati nel [report M3](m3-validation.md), inclusi score, ordine e tie-break.

| Run M4 | SHA-256 identico nelle tre esecuzioni |
|---|---|
| E0 | `6c2e8953aa943e443cce867938b498c28098e395b9b4d11ff605dd482f8566c9` |
| E1 | `564902dffdc2d40afc2ab9e6ab18faa6f12b05ed5432ea4b993e5ea02e518c37` |
| E2 | `7b31797ddaa2083335e18acc7fd3ef4e05fca488bce79200326bcf28ccb911ff` |
| E3 | `cc81866021d146c4127fbef5319f6a637b9ea53ffc31a8ae3020cf4e5b6e1c6d` |
| E4 | `a05eeb85cc2b51fdbcea0c04b27905cf6c5012dce41cd59448128d6013bfad7d` |

## Tempi e limiti

Stesso ambiente M3: Windows, Ryzen AI 7 350, circa 32 GiB RAM, ES 9.5.6 con heap
1 GiB, Python 3.12.2/client 9.5.1. Otto query, warmup e cinque ripetizioni, 40 misure
per profilo. Wall time del RetrievalEngine, inclusi metadata e highlight, senza HTTP.
p95 nearest-rank; cache calda, carico non controllato: misure orientative, non SLA.

| Profilo | Mediana ms | p95 ms |
|---|---:|---:|
| E0 | 16,86 | 22,30 |
| E1 | 15,14 | 19,42 |
| E2 | 16,51 | 25,05 |
| E3 | 45,48 | 214,52 |
| E4 | 15,38 | 22,05 |

Il costo del fuzzy è visibile e va considerato nella demo. L'espansione può
recuperare candidati non pertinenti anche con peso ridotto; E3 non diventa default.
Non confrontare queste latenze direttamente con M3: query e lavoro di highlight differiscono.

## Review qualitativa

Ispezionati risultati, snippet e passaggi del corpo per casi rappresentativi;
il report locale conserva top-5 e corpi per ogni query/profilo. Nessuna qrel prodotta.

- `terremmoto`: E2 non trova risultati, E3 ne trova 144, con notizie di terremoti
  nei primi risultati (2579, 46126, 5619). Verifica funzionale, non misura di recall.
- `terremoto Abruzzo 2009`: E2 trova 1.048 candidati, E3 7.438; l'OR e il fuzzy
  ampliano molto il recupero. In cima restano 26053/26056 e 43994: quest'ultimo
  parla del 2016 citando il 2009. Il boost non risolve l'ambiguità temporale.
- `energia solare`: E4 conserva i 280 candidati E2, cambiando l'ordine; 15204 sale
  al primo posto. Con `"energia solare" Italia`, E4 restituisce solo 15204,
  contro 3.647 candidati E2. Nel corpo compaiono frase e Italia; lo snippet scelto
  mostra Italia ma non necessariamente entrambi i vincoli.
- `"Samantha Cristoforetti" "Stazione spaziale"`: E4 trova tre documenti,
  compreso 41015, sull'iniziativa M'illumino di meno, che cita entrambe le frasi.
  Il vincolo lessicale non garantisce centralità dell'argomento.
- `"di e il"` e la query senza corrispondenze non producono risultati.
- I riquadri degli speciali restano in 26053/26056 e possono comparire negli
  highlight: limite di ingestion M2, non corretto in questa milestone.

## Collaudo software

Esito finale locale: **138 test superati**, nessuno saltato con RUN_INTEGRATION e
RUN_E2E attivi. Ruff superato e `git diff --check` senza errori. Screenshot e trace
dei test browser in `output/playwright/` (ignorati da Git).

Test unitari, integrazione autenticata ed E2E Chromium coprono profili, versioni,
export atomico, refusi/parole brevi, frasi invertite/interrotte, confini dei campi,
stopword, query miste, virgolette tipografiche e malformate, navigazione e XSS.
Verificato anche che l'highlight non alteri score e ordine.

Wheel costruito e installato in ambiente separato, import isolato da site-packages:
ricerche E2, E3 ed E4 riuscite sul corpus reale con risorse incluse nel pacchetto.
Un warning preesistente Starlette/httpx resta non bloccante. CI remota da verificare
dopo il push. Decisioni e compatibilità in [ADR 0005](decisions/0005-advanced-retrieval.md).
