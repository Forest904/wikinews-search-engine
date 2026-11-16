# M5-C — Evidenze della preparazione locale

Data: 2026-11-16. **Preparazione implementata e verificata; pilot umano e gate
scientifico M5-C ancora pendenti.** Nessun giudizio reale prodotto in questa fase.

## Artefatti reali

Le run `experiments/runs/m5c-local-v1` interrogano il corpus M2 di 11.032 documenti
con E0–E4, quattro query e profondità 20: 80 righe per profilo, 400 complessive.
Il pool `m5c-pool-v1` contiene 151 coppie distinte. Non sono run di produzione.

La selezione esplicita contiene 24 coppie, sei per topic, con 12 candidati recuperati
e 12 diagnostici. La diagnosi copre: evento contro semplice confronto numerico;
conseguenze del sisma contro altro terremoto; nucleare civile/militare/diplomazia;
centralità di una persona contro omonimia o stesso ruolo; luogo, anno e conseguenze
di un'alluvione. Nessuna etichetta proposta viene importata. Non si sostiene che
la distribuzione dei casi sia rappresentativa del benchmark.

Il pacchetto cieco finale è `output/m5c-pilot-v2/packet`. Ricostruzione indipendente
in `output/m5c-pilot-repeat` con hash identico; import reale su database temporaneo
verificato e idempotente, senza giudizi. SHA-256 di `packet.json`:

```text
40cc041d666d7751dd7d4f0d31b9a742fe5d1c76e688e0882b275458dabf7227
```

La directory `provenance` separata conserva motivazioni, revisioni, hash del corpo
e rank disponibili. Non va distribuita ai validatori. `m5c-pilot-v1` è una prima
build locale conservata: v2 corregge la codifica delle note di selezione senza
modificare il pacchetto cieco né i testi M2.

Quaranta topic di produzione sono presenti come **bozze**, con 40 riferimenti
di disponibilità nel corpus: 10 per tipologia, 24 development e 16 test. I casi
documentati coprono diversi temi e anni dal 2005 al 2022; ciò non equivale ancora
alla validazione della stratificazione. Query, narrative, esclusioni, varianti e
famiglie richiedono revisione semantica dopo la calibrazione. Le query sono
formulate come bisogni informativi, non copiate automaticamente dai titoli.

## Cambiamenti verificati

- Migrazione SQLite v1→v2 senza perdita di giudizi, utenti o assegnazioni; backup
  e ripristino preservano anche i timer. Nessun database reale esistente è stato
  sovrascritto durante il collaudo.
- Tripla annotazione solo in calibrazione, isolamento degli originali, blocco su
  rinvii/incompletezza, apertura della discussione e conservazione del verbale.
  La tripla calibrazione non produce decisioni gold automatiche.
- Timer espliciti per lettura, compilazione e revisione: checkpoint idempotenti,
  pausa, scheda nascosta, reload, sessioni concorrenti e segmenti incompleti.
- Export con originali, cronologia, tempi e verbale. Report e budget verificati
  con fixture numeriche: 72 letture da 120 secondi e discussione di 10 minuti
  per tre persone = 10.440 secondi-persona di calibrazione.
- Congelamento con controllo della catena di hash, corpus, topic, run, quote,
  selezione, copertura e carichi. Test del rifiuto di evidenze sintetiche e
  profondità incompatibile, output senza sovrascrittura e prompt silver preservato.
- Attivazione idempotente delle assegnazioni congelate, separazione dalle coppie
  solo silver e divieto di aggiungere blocchi dal coordinamento ordinario.

## Collaudo

```powershell
uv run --locked ruff check .
$env:RUN_INTEGRATION = "1"
$env:RUN_E2E = "1"
$env:RUN_ANNOTATION_E2E = "1"
uv run --locked pytest -q
```

Esito della suite completa: **187 test superati**. Le integrazioni usano indici
temporanei; i browser verificano anche le regressioni M5-B. Un warning di
deprecazione già presente riguarda Starlette/httpx. Dopo le ultime modifiche,
**29 controlli mirati superati** su annotazione, pilot e browser. Ruff e
`git diff --check` superati. Screenshot della discussione sintetica:
`output/playwright/m5c/discussion.png`.

## Gate ancora aperti

Occorrono 72 annotazioni umane indipendenti, tempi completi e discussione effettiva.
Non esistono ancora stime reali sostenibili né un budget approvato. Quote e top-k
di produzione, 40 topic definitivi, revisione delle famiglie, run Wikinotizie,
prompt/modello silver calibrati e congelamento finale restano successivi al pilot.
Il timer misura attività dichiarata, non attenzione. I controlli di hash non sono
firme digitali e non certificano la veridicità dei dati dichiarati.

Procedura completa: [m5c-pilot.md](m5c-pilot.md).
