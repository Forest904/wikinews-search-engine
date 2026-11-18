# M5-C — Pilot locale e congelamento

**M5-C chiusa il 18 novembre 2026.** È disponibile il pacchetto congelato per M5-D. La preparazione e il percorso cronometrato sono descritti sotto. Per questa versione si è adottata la modalità con stima dichiarata e revisione del coordinatore. [Risultati e manifest](m5c-validation.md#congelamento-di-produzione-del-18-novembre-2026).

## Materiali pronti

- `benchmarks/topics/calibration-draft.jsonl`: quattro topic, uno per tipologia.
- `benchmarks/pilot/selection-v1.jsonl`: 24 coppie, sei per topic; tre recuperate e
  tre diagnostiche. Le motivazioni sono per il coordinatore, non per gli annotatori.
- `output/m5c-pilot-v2/packet`: pacchetto reale cieco importabile. Testi M2 interi,
  nessun rank, proposta di grado o giudizio altrui. Non condividere `provenance`.
- `benchmarks/topics/production-draft.jsonl`: 40 **bozze aggiuntive**, 10 per tipo,
  6 development e 4 test per tipo. `production-evidence.jsonl` documenta disponibilità
  nel corpus, non rilevanza. Nessun topic è ancora congelato.

Il campione diagnostico serve a discutere ambiguità; non stima la distribuzione dei
gradi del benchmark. Il top-20 delle run del pilot non fissa il top-k di produzione.
Le quattro bozze sono state riconciliate in M5-A; non si importano etichette esterne.
Alcuni testi contengono ancora navigazione editoriale: annotare il contenuto utile,
segnalare i casi ambigui, non correggere il corpus durante la sessione.

### Ricostruzione

Usare directory nuove a ogni esecuzione. Gli output sono ignorati da Git; gli input
di selezione e i topic sono versionati. Le run richiedono gli indici M3/M4 pronti.

```powershell
uv run --locked wikinews-ir benchmark queries --topics benchmarks/topics/calibration-draft.jsonl --protocol configs/evaluation/protocol.yaml --output experiments/runs/m5c-queries-v1
uv run --locked wikinews-ir runs export --queries experiments/runs/m5c-queries-v1/queries.jsonl --output experiments/runs/m5c-local-v1 --top-k 20
uv run --locked wikinews-ir benchmark pool --topics benchmarks/topics/calibration-draft.jsonl --corpus data/processed/m2-v1 --runs experiments/runs/m5c-local-v1 --output experiments/runs/m5c-pool-v1
uv run --locked python scripts/prepare_m5c.py --topics benchmarks/topics/calibration-draft.jsonl --protocol configs/evaluation/pilot.yaml --corpus data/processed/m2-v1 --pool experiments/runs/m5c-pool-v1 --selection benchmarks/pilot/selection-v1.jsonl --output output/m5c-pilot-v2
```

Il builder controlla corpus, hash topic, appartenenza dei candidati recuperati,
24 coppie distinte e validità dei testi. Conserva separatamente provenienza e
pacchetto cieco. Il seed dell'ordine consigliato è `m5c-pilot-1`; i documenti
diagnostici sono scelti esplicitamente, non estratti a sorte.

## Sessione dei tre validatori

1. Seguire [annotation.md](annotation.md) per account personali e avvio locale.
   Eseguire backup prima di aggiornare un archivio esistente. La migrazione SQLite
   1→2 conserva utenti, giudizi e assegnazioni; non avviare una versione precedente
   dell'app sul database aggiornato. Il ripristino accetta backup v1 e v2.
2. Importare soltanto il pacchetto cieco:

   ```powershell
   uv run --locked wikinews-ir annotation import --packet output/m5c-pilot-v2/packet
   ```

3. In `/coordinate#assegnazioni`, per ogni topic scegliere i tre utenti distinti, impostare
   **Documenti in doppio = 6**, scegliere il terzo valutatore e il seed, controllare
   l'anteprima e attivare. Sono 24 coppie distinte e 72 annotazioni.
4. Ogni validatore lavora indipendentemente. Espandere **Tempo operativo** accanto
   al bisogno informativo. Prima di leggere avviare il timer
   **Lettura**; quando si passa a motivazione, citazioni e grado, selezionare
   **Compilazione** e premere nuovamente **Avvia / riprendi**. Il cambio fase mette
   in pausa, non avvia automaticamente la fase successiva.
5. Mettere in pausa per interruzioni. Nascondere la scheda, cambiare documento,
   salvare o cambiare fase mette in pausa; il ritorno richiede ripresa esplicita.
   Non è prevista una deduzione automatica dell'inattività dalla tastiera.
6. I checkpoint cumulativi sono salvati ogni 15 secondi. Dopo un errore di rete o
   chiusura improvvisa, il tempo non confermato rimane sconosciuto. Una sessione
   abbandonata può essere sostituita dopo 45 secondi, conservando il segmento
   incompleto. Il timer non certifica attenzione o identità personale.
7. Astensione e rinvio restano distinti. La discussione si apre soltanto dopo tutte
   le 72 risposte graduate o astensioni; un rinvio blocca l'apertura.
8. La discussione del pilot non è più presente nella pagina coordinatore.
   L'API autenticata `POST /api/annotation/pilot-discussion` resta disponibile
   agli strumenti del protocollo, con i controlli di ruolo e CSRF esistenti.
   L'apertura tramite API congela gli originali e rende disponibili gradi,
   motivazioni, citazioni e testi per una discussione condivisa. Nessuna
   adjudication indipendente è simulata: tutti e tre hanno già letto le coppie.
   Non viene prodotto gold automatico.
9. Registrare minuti effettivi, i tre ID partecipanti e verbale: dubbi, accordi,
   modifiche alla rubrica e casi irrisolti. I minuti della riunione sono moltiplicati
   per i partecipanti nel costo umano. I verbali precedenti restano nell'audit.

Il timer **Revisione** è disponibile per le revisioni indipendenti assegnate nel
flusso di produzione; la discussione comune usa invece la durata registrata nel
verbale. Non si deduce un tempo di adjudication indipendente dal pilot triplo.

## Report e dimensionamento

Scaricare l'export `calibration` dal coordinamento ed estrarre lo ZIP in una
directory nuova. Nel pilot i qrels sono vuoti intenzionalmente: gli originali
sono in `history.jsonl`; durate e verbale in `timing.jsonl` e `discussions.jsonl`.
L'export conserva anche il manifest del pacchetto sorgente.

```powershell
uv run --locked wikinews-ir benchmark pilot-report --source output/pilot-export --output experiments/reports/m5c-measured-v1
uv run --locked wikinews-ir benchmark budget --report experiments/reports/m5c-measured-v1 --plan configs/evaluation/budget-example.json --output experiments/reports/m5c-budget-v1
```

Il file budget è un **esempio da compilare**, non il budget approvato. Usa gli ID
reali del pilot. Dichiara coppie distinte, coppie in doppio, letture per utente e
riserva di revisione in minuti-persona. La riserva viene distribuita equamente
nei tre carichi; modificarne l'entità prima di congelare.

Il report conta astensioni e disaccordi tra coppie di annotatori, escludendo le
astensioni dal denominatore dell'accordo sui gradi. Riporta mediana e percentile
75 (nearest rank) per fase/topic/utente. Non calcola metriche di retrieval.
La stima usa il percentile 75 di lettura + compilazione, somma calibrazione e
riunione già consumate, aggiunge riserva di revisione e letture in doppio.
I tre scenari da 12/15/18 ore richiedono anche carichi individuali entro 4/5/6 ore.

Nel percorso cronometrato, tempi mancanti, segmenti incompleti e pilot non completato impediscono una stima
utilizzabile per congelare. Non riempire i buchi con zero o con valori inventati:
se non è possibile una misura completa, ripetere la sessione di calibrazione in
un nuovo pacchetto/versione e documentare anche il costo già sostenuto. Questa
versione del comando misura un singolo giro: eventuali giri aggiuntivi richiedono
un consolidamento esplicito del budget prima del congelamento.

### Percorso con stima dichiarata

Per il primo pilot aggiungere a `benchmark pilot-report` l’opzione `--coordinator-review benchmarks/pilot/coordinator-review-v1.json`. Il report verifica il manifest sorgente, le 72 risposte e una decisione motivata per ciascun disaccordo. Conserva i tempi osservati e identifica separatamente la stima retrospettiva. Eseguire `benchmark budget` con `configs/evaluation/budget-approved.json`. Il piano approvato di produzione usa questa modalità. La revisione semantica delle famiglie da parte di Codex è dichiarata nel piano di congelamento.

## Congelamento successivo al pilot

Rivedere le 40 bozze e le famiglie semanticamente: ID diversi non provano
indipendenza. Escludere i casi di calibrazione e verificare eventi condivisi tra
topic trasversali. Confermare varianti, temi, periodi e split prima delle run.

Eseguire E0–E4 e Wikinotizie per i topic definitivi tramite i comandi di
[evaluation.md](evaluation.md), indicando un contatto reale nello user-agent
Wikimedia. Conservare archivio live o replay completo. La run esterna del pilot
non è necessaria per questa preparazione locale; quella di produzione è obbligatoria.

Preparare selezione con quote esplicite per tutte le run, pacchetto e piano di
assegnazioni JSONL (`query_id`, `document_id`, `user_id`). Garantire gold su tutti
i topic test e parte del development. Le assegnazioni devono corrispondere ai
conteggi e ai carichi del budget. Non attivare raccolta di produzione in anticipo.

Copiare e compilare `configs/evaluation/freeze-example.json`. I percorsi sono
relativi alla posizione del file piano. Il testo `semantic_overlap_review` deve
documentare la revisione delle famiglie e chi l’ha svolta; il software controlla ID e hash,
non può certificare equivalenza semantica. Calibrare il prompt silver soltanto su
calibrazione/development; indicare modello dichiarato oppure `unknown`.

```powershell
uv run --locked wikinews-ir benchmark freeze --plan configs/evaluation/freeze-approved.json --output output/benchmark-frozen-v1.1
```

L'output contiene `archive/` per il coordinatore e `packet/` cieco importabile.
Nel pacchetto il protocollo diventa `frozen`; `PROMPT.md` è coperto da checksum e
viene riutilizzato da `benchmark silver prepare`. Il modello dichiarato passa nei
metadati del batch, senza essere inventato né verificato automaticamente.
Una nuova versione non sovrascrive output o giudizi precedenti.

Per attivare **esattamente** le assegnazioni gold congelate (senza assegnare le
coppie solo silver), creare prima i tre account previsti dal piano e usare:

```powershell
uv run --locked wikinews-ir annotation activate-freeze --freeze output/benchmark-frozen-v1.1 --actor valutatore-1
```

L'attore deve essere coordinatore. Import e attivazione sono idempotenti; una
divergenza dalle assegnazioni già attive viene rifiutata. I pacchetti prodotti da
`freeze` non consentono blocchi aggiuntivi dal modulo ordinario della UI.

Il congelamento attuale richiede esattamente 40 topic e split 24/16. Una variazione
motivata dal pilot richiede prima aggiornamento esplicito di contratto operativo,
test e roadmap, non un aggiramento dei controlli.
