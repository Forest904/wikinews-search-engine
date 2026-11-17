# UI e UX — polish del 17 novembre 2026

## Intervento

Ricerca, lettura, accesso, annotazione e coordinamento condividono ora navigazione,
tipografia e controlli. Il frontend resta Jinja/CSS/JavaScript nativo; nessuna
migrazione del database o modifica dei contratti di ricerca e valutazione.

| Superficie | Prima | Dopo |
| --- | --- | --- |
| Ricerca | Profili tecnici e istruzioni sempre estese; primo risultato al fondo della schermata | Opzioni richiudibili, nomi descrittivi, intestazione compatta, primo risultato visibile a 1280×720 |
| Articolo | Pagina isolata | Navigazione comune, testo editoriale, fonte e ritorno ai risultati |
| Valutazione | Tre colonne e timer a tutta larghezza | Bisogno informativo orizzontale e timer richiudibile accanto; documento ampio e giudizio laterale |
| Citazioni | Comando soltanto nel giudizio | Comando anche vicino al testo, ricerca con navigazione fra occorrenze, prevenzione dei duplicati |
| Coordinamento | Un'unica pagina lunga | Panoramica, Assegnazioni, Revisioni, Esportazione con URL e conservazione dei moduli |
| Blocchi | Pannello sempre aperto affiancato al modulo | Sezione richiudibile sotto al modulo, aperta dopo creazione ed evidenza della nuova bozza |
| Discussione pilot | Modulo nel coordinamento | Rimossa dalla UI; dati storici e API conservati |

I salvataggi conservano versionamento e idempotenza. Errori e conferme sono vicini
all'azione; le modifiche restano nel modulo dopo errori e sessione scaduta. Dopo
una nuova autenticazione in un'altra scheda è possibile ritentare con lo stesso
account. Il cambio di identità blocca il salvataggio della bozza precedente.

## Evidenze visive locali

Le immagini sono artefatti ignorati da Git, rigenerabili tramite i test browser.

- [Ricerca precedente](../output/playwright/ui-audit-results.png) → [Ricerca aggiornata](../output/playwright/polish/search-results.png)
- [Articolo precedente](../output/playwright/ui-audit-article.png) → [Articolo aggiornato](../output/playwright/polish/article.png)
- [Valutazione desktop 1280×720](../output/playwright/polish/annotation-1280.png)
- [Valutazione desktop 1440×900](../output/playwright/polish/annotation-1440.png)
- [Accesso](../output/playwright/polish/login.png)
- [Blocchi richiudibili](../output/playwright/polish/assignments-collapsed.png)
- [Conferma export test](../output/playwright/polish/export-confirmation.png)
- [Ricerca mobile](../output/playwright/polish/search-390.png)

## Verifica

- Ruff e controllo sintattico Node dei cinque script: superati.
- Suite congiunta: **191 test superati** (178 unitari, 5 browser annotazione,
  8 E2E ricerca con Elasticsearch).
- Dopo le ultime rifiniture: **2 test mirati superati**, inclusa una nuova prova
  di sessione scaduta/cambio account e il flusso ricerca, cronologia e recupero.
  La suite ora comprende 192 casi nei gruppi indicati.
- Verificate larghezze 1440, 1280, 1024 e 390 px; nessun overflow orizzontale
  nelle superfici coperte. Verificato anche reflow a 640 px, equivalente alla
  larghezza CSS di un desktop 1280 px con zoom 200% (non una verifica del comando
  zoom del browser).
- Le principali coppie testo/sfondo hanno contrasto calcolato fra 5,36:1 e
  13,05:1. Focus visibile, etichette e annunci locali implementati; non si tratta
  di una certificazione completa di accessibilità o di un audit con screen reader.
- Copertura di salvataggio, rinvio, conflitto, cronologia, revisione indipendente,
  export, timer attivo richiuso, citazioni Unicode con evidenziazione, validazione,
  navigazione browser e accesso negato.

Un warning preesistente di deprecazione Starlette/httpx resta nella suite unitaria.
Il collaudo usa istanze isolate del codice corrente e fixture; la precedente
istanza sulla porta 8000 non è stata riavviata e non rappresenta questa build.
Nessuna pubblicazione in produzione è stata eseguita.
