# Revisione campione M2

Data: 2026-11-16. Revisore: Codex, confronto testuale assistito tra HTML originale
e output del cleaner; non annotazione umana del benchmark.

Campione di 40 ID distinti: 20 ammessi, 10 esclusi e 10 casi critici.
Selezione deterministica descritta in dataset.md. Evidenza locale completa in
`output/m2-review.json` (ignorata da Git, contiene testi del dump).

Il pilot ha evidenziato avvisi Notizia originale e rimandi ai calendari rimasti
nel corpo: aggiunti selettori mirati e un test di regressione, poi riesaminati
gli stessi ID con il cleaner finale. Fonti separate, tabelle e testo conservati.
Residui non bloccanti: riferimenti editoriali inseriti nella prosa, nomi file di
immagini mancanti e separatori verticali nelle tabelle complesse.

| ID | Gruppo | Titolo | Esito |
|---|---|---|---|
| 53278 | ammesso | Arriva il fronte freddo in Italia: nubifragio a Napoli | Testo, eventuali tabelle e didascalie conservati; fonti separate. |
| 21098 | ammesso | Siena, il Palio di luglio si avvicina | Testo, eventuali tabelle e didascalie conservati; fonti separate. |
| 22244 | ammesso | Arrestato a Toronto il latitante Giuseppe Coluccio | Testo, eventuali tabelle e didascalie conservati; fonti separate. |
| 8554 | ammesso | Pallavolo campionato italiano maschile Serie A2 2006-2007 1° giornata andata | Risultati sportivi conservati; rimando al calendario rimosso. |
| 21226 | ammesso | Tutte le curiosità sul Palio di Siena di oggi | Testo, eventuali tabelle e didascalie conservati; fonti separate. |
| 28047 | ammesso | Italia: concorso n. 140/2009 del SuperEnalotto | Testo, eventuali tabelle e didascalie conservati; fonti separate. |
| 12399 | ammesso | Sanremo giovani, vince Fabrizio Moro con una canzone anti-mafia | Testo, eventuali tabelle e didascalie conservati; fonti separate. |
| 8536 | ammesso | Quattordicesima giornata Serie B Girone D 2006-2007 (rugby) | Risultati e punteggi conservati; rimando al calendario rimosso. |
| 29484 | ammesso | Calcio, Mondiali 2010: disfatta Francia, vola l'Argentina, Grecia ok in rimonta | Testo, eventuali tabelle e didascalie conservati; fonti separate. |
| 51278 | ammesso | Calcio, Premier League 2022-2023: 15ª giornata | Testo, eventuali tabelle e didascalie conservati; fonti separate. |
| 22117 | ammesso | È morto l'ammiraglio Gino Birindelli | Testo, eventuali tabelle e didascalie conservati; fonti separate. |
| 32448 | ammesso | Giro d'Italia 2011: la sesta tappa allo spagnolo Francisco Ventoso | Testo, eventuali tabelle e didascalie conservati; fonti separate. |
| 45499 | ammesso | Calcio, Serie A 2017-2018: 12ª giornata | Testo, eventuali tabelle e didascalie conservati; fonti separate. |
| 19771 | ammesso | Il Governatore Draghi: «La crisi c'è ancora» | Testo, eventuali tabelle e didascalie conservati; fonti separate. |
| 22718 | ammesso | Cevo: la «Croce del Papa» ha bisogno di fondi | Testo, eventuali tabelle e didascalie conservati; fonti separate. |
| 25225 | ammesso | Stasera la Terra tocca il perielio | Testo conservato; marcatori delle note rimossi e note separate. |
| 20300 | ammesso | Estrazione del Lotto, martedì 13 maggio 2008 | Testo, eventuali tabelle e didascalie conservati; fonti separate. |
| 16101 | ammesso | Riapre oggi la reggia di Venaria | Testo, eventuali tabelle e didascalie conservati; fonti separate. |
| 51710 | ammesso | Calcio, Serie B 2022-2023: 26ª giornata | Testo, eventuali tabelle e didascalie conservati; fonti separate. |
| 16808 | ammesso | Montezemolo: "In questo Governo non c'è coesione" | Testo, eventuali tabelle e didascalie conservati; fonti separate. |
| 2650 | escluso | Striscia di Gaza sgombero dei coloni israeliani 2005 | Categoria Pubblicati assente; esclusione coerente con la policy. |
| 3525 | escluso | Tredicesima giornata Serie A Girone A 2005-2006 (rugby) | Categoria Pubblicati assente; esclusione coerente con la policy. |
| 22936 | escluso | Calcio Champions League 2008-2009 | Aggregatore sportivo, escluso. |
| 4076 | escluso | Quattordicesima giornata Serie B Girone D 2005-2006 (rugby) | Categoria Pubblicati assente; esclusione coerente con la policy. |
| 21491 | escluso | Speciale XXIX Olimpiade estiva/Calendario specifico/Calcio | Calendario sportivo, escluso. |
| 29977 | escluso | Calcio, Coppe europee: il percorso delle squadre inglesi | Pagina riepilogativa sportiva, esclusa. |
| 45784 | escluso | Muore Stephen Hawking | Notizia plausibile esclusa per assenza di Pubblicati: limite di copertura. |
| 51776 | escluso | Superbonus: verrà rivisto dal nuovo governo. Usciti nuovi dati ENEA | Bozza con avviso lavori in corso, esclusa. |
| 2440 | escluso | Decima giornata Super 10 2005 | Categoria Pubblicati assente; esclusione coerente con la policy. |
| 51361 | escluso | Truffe a Roma: rubavano case falsificando gli atti | Pagina senza corpo giornalistico, esclusa per assenza di Pubblicati. |
| 17527 | critico | Italia: concorso n. 142/2007 del SuperEnalotto | Testo, eventuali tabelle e didascalie conservati; fonti separate. |
| 6726 | critico | Lecce: a 11 mesi muore soffocata da un tappo | Testo, eventuali tabelle e didascalie conservati; fonti separate. |
| 18130 | critico | Shuttle: si riuniscono oggi i responsabili di missione per decidere la partenza dell'Atlantis | Testo, eventuali tabelle e didascalie conservati; fonti separate. |
| 48678 | critico | Evanescence: uscito il nuovo singolo | Testo, eventuali tabelle e didascalie conservati; fonti separate. |
| 50436 | critico | Costituzione Coordinamento Toscano Caritas ETS | Avviso Notizia originale rimosso; data con carattere direzionale resta invalid/null. |
| 4539 | critico | Prima giornata Sei Nazioni 2006 | Due date editoriali discordanti: ambiguous/null; risultati conservati. |
| 1055 | critico | Speciale elezioni amministrative 2005 | Tre date nel contenuto: ambiguous/null; tabelle elettorali conservate. |
| 43200 | critico | Viaggio umanitario del CIS in Malawi-Zambia | Reportage lungo conservato, incluse didascalie; residuo nome file documentato. |
| 32804 | critico | La "Provaccia" del Palio di Siena di luglio 2011 alla Tartuca | Testo, eventuali tabelle e didascalie conservati; fonti separate. |
| 44223 | critico | Yoshinori Ōsumi vince il premio Nobel per la medicina | Testo, eventuali tabelle e didascalie conservati; fonti separate. |
