# Roadmap di NewsFinder — Verso la ricerca di Wikinotizie

## Da chiudere per la consegna

- [ ] Finalizzare le slide a partire dalla [relazione](report/newsfinder.pdf). In locale è già presente una presentazione PowerPoint. Verificarne contenuto, assenza di codice nelle slide e inclusione nella consegna.
- [ ] Provare l’esposizione di circa 20 minuti e registrare durata e punti da accorciare. La dimostrazione pratica ha un copione separato.
- [ ] Eseguire la demo sulla macchina e sulla rete dell’aula, con indice locale pronto. Registrare esito, problemi e ripristino nel verbale. [Copione della demo](consegna/demo.md) · [Verbale di collaudo](operazioni.md#collaudo)

**Aggiornata il 19 novembre 2026.** La consegna documenta la release v1.0.0. Le sei milestone successive riguardano lo sviluppo futuro su Elasticsearch e possono avanzare indipendentemente dalla prova in aula. [Requisiti dell’homework](sistema.md)

## Base della release

Il [sistema](sistema.md) cerca su [11.032 articoli](dataset.md). E1 è il riferimento lessicale selezionato sul development. La [valutazione](evaluation.md#risultati-sperimentali) raccoglie risultati e limiti; le [operazioni](operazioni.md#collaudo) documentano il collaudo.

## Obiettivo e criterio di confronto

Avvicinare la ricerca lessicale di NewsFinder al comportamento verificabile di **Wikinotizie in italiano** e misurare se il risultato resta utile ai lettori. Il confronto storico rende necessarie entrambe le verifiche. Sul test già utilizzato, E1 ha ottenuto una nDCG@10 gold superiore alla run Wikimedia proiettata sul corpus. Campione, pooling e differenze di snapshot limitano l’interpretazione. Somiglianza degli elenchi e rilevanza umana avranno quindi misure distinte. [Risultati per profilo](evaluation.md#risultati-sperimentali)

Il riferimento esterno è il sito italiano osservato a una data dichiarata. Lo snapshot locale precede la chiusura di Wikinotizie del maggio 2026. Usare risposte datate del sito per verificare il comportamento del motore e fonti storicamente compatibili per arricchire l’indice locale. Conservare E0–E4, corpus, run e giudizi della release come base riproducibile. [Archivio italiano](https://it.wikinews.org/wiki/Pagina_principale) · [Protocollo di valutazione](evaluation.md)

## 1. Fissare il comportamento di riferimento

**Dipendenza:** release v1.0.0. Preparare un campione versionato di ricerche su titoli, eventi, termini distribuiti su più campi, frasi, apostrofi, refusi e query senza risultati. Riutilizzare le run esterne disponibili dove contengono già l’evidenza richiesta. Per ogni nuova osservazione conservare data, query, parametri, namespace, ID e ordine dei risultati, revisione quando disponibile, documento indicizzato e richiesta generata. Archiviare anche configurazione e provenienza del codice consultato. [Configurazione locale](https://it.wikinews.org/w/api.php?action=cirrus-config-dump&format=json) · [Profili CirrusSearch](https://www.mediawiki.org/wiki/Extension:CirrusSearch/Profiles)

Usare come caso guida `terremoto Abruzzo`: il dump della richiesta mostra il profilo per campo, il filtro sul namespace principale, i rami di near match, l’highlighting e i riordinamenti. Per ogni funzione indicare se è osservata sul sito, descritta nella documentazione generale o ancora da verificare. Partire dai token italiani e dal percorso effettivo di completamento per chiudere le due incertezze emerse nell’indagine. [Query generata](https://it.wikinews.org/w/api.php?action=query&list=search&srsearch=terremoto%20Abruzzo&cirrusDumpQuery=1&format=json) · [Risultati](https://it.wikinews.org/w/api.php?action=query&list=search&srsearch=terremoto%20Abruzzo&format=json)

**Criterio di uscita:** un altro sviluppatore può ispezionare offline esempi, risposte e matrice comportamento–evidenza. Ogni lacuna ha una verifica prevista o un limite dichiarato.

## 2. Ricostruire ciò che il motore può cercare

**Dipendenze:** manifest M2 e casi della milestone 1. Produrre due viste dello stesso snapshot. La prima mantiene gli 11.032 ID accademici. La seconda parte da tutti i record disponibili del namespace principale, riconcilia le revisioni e classifica articoli, speciali, redirect e altre pagine. Un redirect può contribuire come titolo alternativo della destinazione. Conservare la distinzione fra pagina indicizzata e risultato autonomo. [Policy del corpus](dataset.md) · [Filtri applicati dal sito](https://it.wikinews.org/w/api.php?action=query&list=search&srsearch=terremoto%20Abruzzo&cirrusDumpQuery=1&format=json)

Affiancare al corpo giornalistico una vista del testo espanso recuperabile dall’HTML. Estrarre con provenienza titolo, apertura, intestazioni, categorie, template identificabili, collegamenti, fonti e redirect. Tenere distinti data editoriale, data citata dalla fonte, eventuale data dell’evento e timestamp di revisione. Registrare per campo origine, copertura e valori mancanti. Per grafo e dipendenze usare arricchimenti datati e compatibili quando reperibili. Conteggiare link locali, rimandi a Wikipedia e URL di fonte separatamente. [Template Data](https://it.wikinews.org/w/index.php?title=Template:Data&action=raw) · [Template Pubblicato](https://it.wikinews.org/w/index.php?title=Template:Pubblicato&action=raw)

**Criterio di uscita:** due manifest con conteggi e differenze spiegate per ID e revisione. Per la pagina 26053 confrontare sommario dello speciale, primo paragrafo, data del 7 aprile 2009, categoria editoriale e origine dei link con il documento ufficiale. Verificare anche uno speciale e un redirect con destinazione assente o presente nel dump. Documentare i dati irrecuperabili e gli effetti previsti. [Revisione campione](https://it.wikinews.org/w/index.php?title=Nuova_fortissima_scossa_di_terremoto_in_Abruzzo&oldid=964970) · [Documento CirrusSearch](https://it.wikinews.org/w/api.php?action=query&prop=cirrusdoc&pageids=26053&format=json)

## 3. Riprodurre il recupero lessicale su Elasticsearch

**Dipendenze:** campione di riferimento e viste del corpus. Introdurre mapping e profilo sperimentale versionati, selezionabili dal medesimo motore usato da Web, API e valutazione. Riprodurre prima l’ammissione dei candidati con AND sul campo aggregato o sulla variante plain e un ramo alternativo di near match per titoli e rimandi. Ricostruire poi il punteggio BM25 per campo, le varianti analizzate e la combinazione fra apertura e corpo. Ricavare i coefficienti dalla query effettiva distinguendo le clausole di ranking da quelle di evidenziazione. [Albero della query italiana](https://it.wikinews.org/w/api.php?action=query&list=search&srsearch=terremoto%20Abruzzo&cirrusDumpQuery=1&format=json)

**Criterio di uscita:** fixture separate per inclusione e ordine. Coprire termini distribuiti tra titolo e testo, titolo alternativo, frase nel box condiviso, accenti, apostrofi tipografici e flessioni. Registrare i token locali e, quando osservabili, quelli di riferimento. Per ogni differenza dovuta ad analyzer, plugin o versione mostrare una query interessata e il risultato ottenuto. [Baseline esistenti](dataset.md) · [Configurazione delle similarità](https://it.wikinews.org/w/api.php?action=cirrus-config-dump&format=json)

## 4. Riprodurre i tre riordinamenti

**Dipendenza:** profilo lessicale verificato. Implementare e misurare un segnale alla volta nell’ordine osservato. Registrare numero di shard, finestre, copertura dei link, sorgente del timestamp e istante fissato per le run. [Sezione rescore della richiesta](https://it.wikinews.org/w/api.php?action=query&list=search&srsearch=terremoto%20Abruzzo&cirrusDumpQuery=1&format=json)

| Segnale | Comportamento osservato da riprodurre | Controllo mirato |
|---|---|---|
| Prossimità | Per 2–10 token, frase con slop 1, peso esterno 10 e finestra di 512 candidati per shard. | Confrontare parole adiacenti, distanti e query oltre il limite. |
| Link entranti | Bonus additivo pari a 13 × L^0,7 / (L^0,7 + 30^0,7), finestra 8.192 per shard. Ricostruire il conteggio considerando le destinazioni dei redirect. | A zero link il bonus è zero, a 30 è 6,5. Distinguere uno zero osservato da un dato mancante. |
| Freschezza della revisione | Moltiplicatore 0,4 + 0,6 × 2^(−d/160), con d in giorni e finestra 8.192 per shard. | A 0, 160 e 320 giorni attendere 1,00, 0,70 e 0,55. Provare una notizia antica modificata di recente. |

**Criterio di uscita:** test numerici, run ripetibili e confronto dell’ordine dopo ogni aggiunta. Spiegare almeno uno spostamento reale e quantificare quante pagine hanno link o date insufficienti per un confronto fedele. [Costruzione dei link entranti](https://github.com/wikimedia/mediawiki-extensions-CirrusSearch/blob/master/includes/BuildDocument/RedirectsAndIncomingLinks.php)

## 5. Completare l’esperienza di ricerca

**Dipendenze:** campi verificati nella milestone 2 e recupero della milestone 3. Per ogni funzione descrivere input e risposta API, comportamento visibile dalla UI e copertura del dato sottostante. Conservare il dettaglio articolo con il suo testo redazionale anche quando la corrispondenza deriva dal testo espanso. [Sintassi CirrusSearch](https://www.mediawiki.org/wiki/Help:CirrusSearch)

| Funzione | Prova di accettazione |
|---|---|
| Snippet e highlight | Confrontare frammenti dal corpo, dal titolo e da un box. Controllare evidenziazione anche quando i termini cercati compaiono in parti distinte. |
| Virgolette e operatori | Provare frase esatta, titolo, categoria, template e sorgente. Per insource dichiarare quali revisioni hanno wikitesto disponibile e rendere esplicita in UI/API l’eventuale copertura parziale. |
| Correzione dopo l’invio | Su un refuso osservare separatamente risultati originali e proposta correttiva. Verificare anche il caso senza proposta. |
| Completamento durante la digitazione | Verificare sul sito prefisso, titolo alternativo e ordine dei suggerimenti. Confrontarli con il completamento locale e misurare la latenza di questo percorso. |

**Criterio di uscita:** prove API e browser per ciascuna riga con esempi riproducibili. Allegare le divergenze osservate rispetto al sito, incluse le funzioni verificabili solo in parte. [Descrizione del completamento](https://www.mediawiki.org/wiki/Extension:CirrusSearch/CompletionSuggester/en)

## 6. Valutare il profilo e decidere il rilascio

**Dipendenze:** profili versionati e riferimenti congelati. Avviare la progettazione del protocollo dalla prima milestone. Prima del confronto finale preregistrare topic, profondità, criterio di riconciliazione, parametro della Rank-Biased Overlap (RBO), margine accettabile sulla rilevanza, guadagno di fedeltà richiesto e budget di latenza. Motivare le soglie su development e sul costo operativo della demo. [Protocollo storico](evaluation.md) · [Misure di prestazione](evaluation.md#prestazioni)

- **Fedeltà.** Confrontare E1 e il candidato con la stessa run ufficiale datata. Riportare copertura degli ID, sovrapposizione in top 10 e RBO. Pubblicare sia la misura end-to-end sia quella dopo proiezione sulle pagine comuni, dichiarando dove una lista ha meno di dieci risultati. Separare differenze di snapshot e revisioni da ammissione dei candidati e ordine.
- **Rilevanza.** Eseguire il tuning su development. Ampliare il pool con i risultati introdotti dal candidato, giudicarli alla cieca e usare un nuovo campione indipendente per la decisione finale. Riportare almeno nDCG@10 e P@5 gold, copertura dei giudizi e variabilità per topic. Mantenere identificabili qrels, run e test storico già consultato.
- **Prestazioni e diagnosi.** Ripetere il protocollo di latenza a parità di macchina, query e condizioni di cache. Riportare p50, p95 ed errori. Per le divergenze maggiori risalire alla prima causa verificabile fra corpus, revisione, testo espanso, analisi linguistica e ranking.
- **Promozione.** Rendere il profilo predefinito quando supera la soglia di fedeltà e rispetta margine di rilevanza e budget di latenza. Con evidenza insufficiente lasciarlo selezionabile come sperimentale. Mantenere E1 disponibile e verificare il ritorno al profilo precedente da Web e API.

**Criterio di uscita:** rapporto riproducibile con manifest di corpus, indici, profili, query, giudizi e ambiente, risultati per entrambi i perimetri e decisione motivata sul profilo predefinito. La riproduzione offline usa il riferimento archiviato; una successiva osservazione del sito apre un confronto datato distinto. [Risultati congelati della release](evaluation.md#risultati-sperimentali) · [Architettura attuale](sistema.md)
