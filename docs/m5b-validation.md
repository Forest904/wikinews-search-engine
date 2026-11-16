# M5-B — Verifica locale dello strumento di annotazione

Data: 2026-11-16. Stato: implementata e verificata su fixture sintetiche.
Nessun gold/silver reale prodotto e nessuna pubblicazione online eseguita.

## Percorso verificato

Tre sessioni Chromium indipendenti rappresentano Alice (coordinatrice e annotatrice),
Bob (annotatore) e Carol (revisora). Il pacchetto sintetico contiene un topic di
calibrazione e quattro documenti; tutti sono assegnati in doppio nel test principale.

1. Alice prepara e attiva un blocco dalla pagina di coordinamento.
2. Alice e Bob aprono la stessa coppia senza vedere il giudizio dell'altro.
3. Ricerca nel testo e selezione di citazioni funzionano anche con caratteri
   fuori dal BMP e con offset successivi a questi caratteri.
4. I due utenti salvano gradi discordanti. La dashboard mostra una revisione pendente.
5. Solo Carol è selezionabile come revisora della coppia. La sua coda mostra gli
   originali e permette una finale separata.
6. Alice scarica l'archivio gold consolidato; il contenuto è compatibile con M5-A.

Un secondo percorso verifica bozza rinviata, reload e ripresa, errore HTTP 503
simulato senza perdita del form né avanzamento, conflitto fra schede aperte sulla
stessa versione e cronologia delle revisioni.

## Risultati automatici

Esecuzione completa locale:

```powershell
$env:RUN_INTEGRATION = "1"
$env:RUN_E2E = "1"
$env:RUN_ANNOTATION_E2E = "1"
uv run --locked pytest -q
```

**173 test superati**, inclusi retrieval/integration con Elasticsearch reale,
browser di ricerca e i due test browser annotazione. Un warning di deprecazione
Starlette/httpx già presente non influisce sull'esito. Ruff superato.

I test del servizio coprono password, idempotenza, isolamento, autorizzazioni,
CSRF, revoca, limite login, manifest alterati, protocollo test, quote e assegnazioni
congelate, finalizzazione singola/concordante, disaccordi, astensione finale,
invalidazione delle finali, revisione su versioni obsolete, export e cronologia.
Salvataggi simultanei di utenti distinti persistono entrambi; due salvataggi della
stessa versione hanno un solo vincitore. Backup, ripristino e riapertura conservano
account, pacchetti, giudizi e decisioni; la destinazione esistente non viene sovrascritta.

La CI include un job `annotation-browser` senza Elasticsearch. L'esito remoto
rimane da verificare dopo il push.

## Controllo UI

Ispezionati screenshot desktop 1440 px e mobile 390 px: pannelli leggibili,
gerarchia criteri/documento/giudizio, feedback del salvataggio, avanzamento,
cronologia e assenza di overflow orizzontale. La pagina di coordinamento distingue
conteggi, preparazione, revisione ed export. Su mobile sono disponibili collegamenti
rapidi alle tre sezioni.

Artefatti rigenerabili e ignorati da Git:

- `output/playwright/annotation/annotator-desktop.png`
- `output/playwright/annotation/annotator-mobile.png`
- `output/playwright/annotation/coordinator-desktop.png`
- `output/playwright/annotation/gold-calibration.zip`

## Gate e limiti

Il gate locale M5-B è soddisfatto: il percorso multiutente persiste i dati e lavora
senza chiamate live al retrieval, al Web o a un LLM. Le quote della fixture non
fissano quelle del benchmark. SQLite è previsto su un singolo server con volume
locale; hosting, HTTPS, accesso da macchine distinte e prova di ripristino online
rimangono M7-A. Pilot, misure dei tempi e raccolta reale rimangono M5-C/D.

Guida operativa: [annotation.md](annotation.md). Decisioni:
[ADR 0006](decisions/0006-collaborative-annotation.md).
