# M5-C — Evidenze della preparazione locale

Data: 2026-11-16. **Preparazione implementata e verificata; pilot umano e gate
scientifico M5-C ancora pendenti.** Dopo la preparazione sono state prodotte e
importate le prime 24 silver label reali di calibrazione, descritte nel diario sotto.

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

## Diario — prima raccolta silver indipendente, 16 novembre 2026

Eseguito il primo batch reale in una nuova chat Codex in VS Code, nel workspace
`output/codex-pilot-silver-001`, secondo la procedura riferita dall'operatore.
Modello dichiarato: **GPT-6.0-Astra**; operatore `lucap`, batch `pilot-silver-001`,
esecuzione `chat-pilot-001`. Il modello è registrato in `model_declared` all'import;
il valore `declared_model=unknown` del pacchetto iniziale non è una contraddizione:
la scelta non era dichiarata alla preparazione. La pipeline non verifica il modello.

Il pacchetto deriva da `output/m5c-pilot-v2/packet`: quattro topic di calibrazione,
sei coppie per topic, testi M2 completi e protocollo `m5c-pilot-1` ancora **draft**.
La valutazione è indipendente dai giudizi umani: il pacchetto fornito al modello
non contiene gold, ranking o precedenti proposte di etichetta; prompt e workspace
prescrivono di usare solo bisogno informativo, rubrica e testi. Questa è una
separazione organizzativa, non una prova tecnica degli accessi effettuati nella chat.

### Procedura e artefatti conservati

1. Preparazione del workspace con `benchmark silver prepare` dal pacchetto cieco.
2. Nuova chat, selezione del modello e uso del `PROMPT.md` del batch; produzione di
   `judgments.jsonl` con grado, motivazione e citazioni del corpo degli articoli.
3. Validazione completa e import tramite `benchmark silver import`, conservando
   originale, giudizi normalizzati, report di validazione e metadati.
4. Export separato tramite `benchmark export-qrels --source silver`.

| Artefatto locale | Percorso |
|---|---|
| Input ciechi, prompt e output della chat | `output/codex-pilot-silver-001/` |
| Import verificato | `experiments/runs/pilot-silver-001/` |
| Qrels silver | `experiments/runs/pilot-qrels-silver-001/qrels_silver.tsv` |

Queste directory sono ignorate da Git: il diario versiona le evidenze, non archivia
i dati. Conservare anche le directory originali per il report e la riproducibilità.
La procedura generale e i comandi sono in [evaluation.md](evaluation.md).

### Primi risultati e verifica

| Esito | Numero |
|---|---:|
| Coppie attese / giudicate | 24 / 24 |
| Grado 2 | 13 |
| Grado 1 | 2 |
| Grado 0 | 9 |
| Astensioni / coppie mancanti | 0 / 0 |

Rieseguita la validazione completa: `valid=true`, nessun errore o coppia mancante.
Verificati schema, revisioni, hash dei testi, citazioni e checksum dei tre bundle
(batch, import, qrels). L'originale importato coincide con il testo dell'output
della chat; il suo hash sorgente corrisponde al manifest. Giudizi normalizzati e
24 righe dei qrels coincidono con l'output validato.

Fingerprint SHA-256 per il futuro report:

- Prompt: `733762f3da16c6c4f5f4e99a888a601e195ced03ec0a604d15dcc10dca051f46`.
- Output sorgente della chat: `8e53a73fc4178f0949c5e6e8e16aa7c74162afa8fb6bc0204e39e08681f21afa`.
- Giudizi normalizzati: `df327333f217b819846165f3d469c866eda911cd3dbcf1f03b5980659188d68c`.
- Qrels silver: `0b8d339f6003c576a01fee215a7234181d5764781464572d49a1014e6b7b70e7`.
- Il pacchetto conserva l'hash `40cc041d…abf7227` riportato integralmente sopra.

Una prima lettura delle motivazioni, con approfondimento di alcuni casi limite,
ha trovato giudizi plausibili rispetto alle rubriche, non certificato la loro
accuratezza. Esempi da discutere dopo le valutazioni umane indipendenti: P01/26210,
G8 all'Aquila, grado 2 per il legame sostanziale con la ricostruzione; P02/11351,
composizione musicale iraniana, grado 1 per l'informazione secondaria sull'impiego
energetico, caso di confine sulla concretezza dell'informazione richiesta.
Non sono state modificate le label durante questa review.

Sono **silver di calibrazione**, non gold né benchmark finale. La distribuzione
dei voti non misura la qualità dei sistemi E0–E4 e il campione diagnostico non è
rappresentativo. Nessun accordo gold/silver o metrica di retrieval è stato calcolato.
La baseline Wikimedia live non è ancora raccolta nel progetto.

Prossimo passo: raccogliere le 72 valutazioni dei tre validatori sulle stesse
24 coppie senza mostrare le silver, discutere i disaccordi e misurare i tempi.
Solo successivamente rivedere rubriche e prompt, dimensionare la produzione,
confermare i topic, raccogliere le run anche Wikimedia e congelare il protocollo.

## Gate ancora aperti

Occorrono 72 annotazioni umane indipendenti, tempi completi e discussione effettiva.
Non esistono ancora stime reali sostenibili né un budget approvato. Quote e top-k
di produzione, 40 topic definitivi, revisione delle famiglie, run Wikinotizie,
prompt/modello silver calibrati e congelamento finale restano successivi al pilot.
Il timer misura attività dichiarata, non attenzione. I controlli di hash non sono
firme digitali e non certificano la veridicità dei dati dichiarati.

Procedura completa: [m5c-pilot.md](m5c-pilot.md).
