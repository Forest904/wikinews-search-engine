# ADR 0007 — Calibrazione tripla e congelamento verificabile

Data: 2026-11-16. Stato: adottato per la preparazione locale M5-C.

## Decisione

Il pilot usa quattro topic e 24 coppie, tutte affidate ai tre validatori. È
separato dalla produzione: nessuno dei tre è un revisore indipendente delle
stesse coppie. L'apertura della discussione richiede tutte le risposte graduate
o astensioni, congela gli originali e registra un verbale; non produce gold.
Il flusso ordinario con doppia annotazione e terzo revisore rimane invariato.

Lettura e compilazione hanno timer espliciti; la discussione registra durata e
partecipanti. I checkpoint persistono quantità cumulative, consentendo retry
senza doppio conteggio. Segmenti interrotti conservano l'ultimo tempo confermato;
non si deducono intervalli mancanti dai timestamp dei giudizi.

Il dimensionamento usa percentile 75, costo di calibrazione già sostenuto e
riserva esplicita di revisione. Il congelamento verifica riferimenti e conteggi,
pubblica un archivio completo per il coordinatore e un pacchetto cieco separato,
senza sovrascrivere artefatti precedenti. Il prompt congelato viene trasferito
nei batch silver. Le assegnazioni gold sono attivate dal piano esatto, non
ricostruite manualmente a partire dall'intero pacchetto silver.

## Conseguenze

SQLite passa alla versione 2 con migrazione conservativa. Il vecchio codice
rifiuta il nuovo database; conservare un backup precedente all'aggiornamento.
I pacchetti M5-A/B restano validi e il nuovo percorso non richiede Web o LLM per
annotare. Le run di produzione Wikinotizie sono un requisito del congelamento,
non della preparazione del pilot locale.

Quaranta topic e split 24/16 sono controlli espliciti del comando di congelamento:
una variazione motivata dai dati richiede revisione documentata. La verifica delle
famiglie richiede anche controllo umano: identificatori diversi non garantiscono
assenza di contaminazione semantica. Nessuna evidenza sintetica chiude M5-C.
