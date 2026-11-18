# Verifica M6-A del 18 novembre 2026

La CLI ha generato un report su due ranking sintetici. La fixture contiene tre topic development
e un topic test per verificare il filtro di split. [Comandi per riprodurre il report](evaluation.md#riprodurre-il-report-m6-a).

| Caso sintetico | Risultato verificato |
|---|---|
| Topic evento, unico documento rilevante al rank 2 dopo un’astensione | nDCG@10 = 1/log₂(3) ≈ 0,63093, P@5 = 0,2, MRR@10 = 0,5 |
| Stessi documenti, ordine invertito nella baseline | MRR@10 = 1 |
| Due risultati, uno giudicato | Copertura = 1/2 sia a 5 sia a 10 |
| Topic con gradi validi e run vuota | P@5 = 0, copertura N/D |
| Topic senza giudizi | Escluso dalla media, presente nella tabella per query |
| Due coppie condivise con gradi (0,0) e (2,1) | Macro-F1 = 1/3, kappa lineare = 0,5, un disaccordo |
| Intersezione vuota o classe costante | Kappa N/D |

Il controllo automatico comprende il rifiuto di un checksum alterato e di uno split
incompatibile con l’export M5-B. I test M5 verificano anche la lettura degli export
gold e silver generati dai rispettivi flussi su dati sintetici.

Ruff superato. La suite offline ha completato 212 test con successo, 10 saltati e
17 esclusi dal filtro integration/e2e. Il gate riguarda la pipeline. La selezione del
profilo e la valutazione finale attendono i giudizi consolidati per M6-B.
