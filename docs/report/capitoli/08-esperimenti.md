\clearpage
# Risultati sperimentali

Prima del test abbiamo fissato la regola di scelta: massimizzare nDCG@10 sul gold di sviluppo, usare P@5 in caso di parità e infine l’ordine dei profili. E1 prevale sui 24 topic di sviluppo (0,6659 in nDCG@10 e 0,2833 in P@5). Abbiamo quindi congelato E1 prima di aprire il test. Il confronto finale usa i 16 topic riservati e classifiche archiviate fino a 100 posizioni. Anche il confronto Wikimedia usa una classifica salvata, proiettata sui documenti del corpus [@esperimenti].

La Tab. \ref{tab:test} riporta i risultati finali secondo le tre metriche.

\tabletitle{test}{Confronto sul test con giudizi umani. nDCG e precisione su 16 topic, MRR sui quattro topic evento}

\input{figure/risultati-test.tex}

**Come leggere i valori.** P@5 conta quanti dei primi cinque risultati hanno grado almeno 1 e divide per cinque. MRR@10 considera la posizione del primo pertinente sui quattro topic di tipo evento: trovarlo al secondo posto vale $1/2$. nDCG@10 assegna più peso ai gradi alti e alle prime posizioni, poi divide per il guadagno dell’ordine ideale ricavato dai giudizi [@dcg]. Con due soli documenti di grado 2 e 0, mettere il pertinente al primo posto dà 1; spostarlo al secondo riduce il rapporto a $1/\log_2(3)$, circa 0,63.

E1 supera E0 di 0,0596 in nDCG@10 sul test. Il confronto cambia se chiediamo quanto presto emerge il primo risultato utile nei topic evento: su quei quattro casi E0 e Wikimedia ottengono 0,7500 contro 0,6250 di E1. Sono differenze descrittive su un campione piccolo. La scelta di una metrica determina quale esperienza del lettore stiamo sintetizzando.

\clearpage
## Discussione e analisi di sensibilità

La Tab. \ref{tab:ranghi} identifica i documenti ai primi due ranghi per Q37.

\tabletitle{ranghi}{Prime due posizioni sulla query Q37 e relativi giudizi umani}

| Posizione su Q37 | E0 · standard | Grado gold | E1 · italiano | Grado gold |
|:--|--:|:--|--:|:--|
| 1 | 21736 | Senza giudizio | 1374 | 2 |
| 2 | 27073 | 1 | 2273 | 2 |

La prima riga riporta al documento da cui siamo partiti. L’analizzatore italiano porta in testa proprio la cronaca tra Osaka e Kobe. Il guadagno nDCG@10 su Q37 è 0,6994. Su Q09, invece, il documento 4230 di grado 2 scende dalla prima alla seconda posizione passando da E0 a E1 e la metrica perde 0,3691. Aumentando il peso del titolo con E2, lo stesso articolo esce dai primi dieci. Il vantaggio medio di E1 convive quindi con errori ben localizzati.

La Tab. \ref{tab:sensibilita} riunisce le verifiche sulle principali fonti di variazione.

\tabletitle{sensibilita}{Effetto della copertura e delle varianti di query sui risultati}

| Verifica di sensibilità | Risultato osservato |
|:--|:--|
| Copertura gold di E1 sul test | 31 posizioni giudicate su 80 a profondità 5; 43 su 160 a profondità 10. |
| Rimozione dei risultati senza giudizio | Ricomponendo la classifica sui primi 100, nDCG@10 di E1 passa da 0,6558 a 0,7842. |
| Query con refusi | Sul test la perdita di nDCG è 0,1434 per E2 e 0,1401 per E3. |
| Query con più vincoli | In tutti i dieci casi osservati E4 ed E2 danno lo stesso ordine. Nessuna query contiene una frase obbligatoria fra virgolette. |

Nella misura principale un documento senza giudizio mantiene la sua posizione e riceve guadagno nullo. Per capire quanto pesi questa scelta, siamo partiti dallo stesso elenco restituito dal motore. Entro i primi 100 risultati abbiamo rimosso quelli privi di giudizio e ricalcolato la metrica. I documenti giudicati sono avanzati di posizione: è questo passaggio a far salire nDCG@10 da 0,6558 a 0,7842. Lo scarto fra i valori mostra la sensibilità della conclusione alla copertura. Rimane sconosciuto il numero totale di articoli pertinenti allo stesso bisogno presenti negli 11.032 documenti. Di conseguenza, il richiamo assoluto non è stimabile da questo pool.

\clearpage
## Qualità e latenza sull’intero archivio

Sui 16 topic con giudizi umani E1 raggiunge 0,6558 in nDCG@10 e il profilo semantico 0,5967. Passando da E1 al semantico, quattro topic migliorano, otto mantengono lo stesso punteggio e quattro peggiorano. La differenza media è −0,0591. L’intervallo bootstrap appaiato al 95%, ottenuto ricampionando 5.000 volte i topic, va da −0,2286 a +0,0859 e comprende lo zero. Anche la copertura pesa sul confronto: dei 160 risultati restituiti nei primi dieci posti, il gold ne copre 43 per E1 e 23 per il semantico.

\tabletitle{latenze-locali}{Latenza del motore sul corpus completo. Tempi in millisecondi, riscaldamento escluso}

| Campagna | Profilo | Richieste misurate | Mediana (ms) | P95 (ms) |
|:--|:--|--:|--:|--:|
| Lessicale | E0 | 234 | 9,7 | 24,9 |
| Lessicale | E1 | 234 | 10,3 | 16,4 |
| Lessicale | E2 | 234 | 10,5 | 15,7 |
| Lessicale | E3 | 234 | 63,8 | 109,6 |
| Lessicale | E4 | 234 | 11,6 | 19,9 |
| Confronto diretto | E1 | 26 | 10,5 | 14,5 |
| Confronto diretto | Semantico | 26 | 460,5 | 490,1 |

Nella Tab. \ref{tab:latenze-locali} E3, il profilo che gestisce i refusi, presenta la mediana più alta fra i cinque lessicali. La campagna ha completato senza errori 1.560 richieste, di cui 390 di riscaldamento e 1.170 misurate. Nel confronto diretto lo stesso insieme di input richiede circa 450 ms in più alla mediana per la ricerca semantica, che comprende la generazione dell’embedding della query.

Il confronto vettoriale sui 16 topic restituisce gli stessi insiemi di dieci documenti con ricerca esatta e con l’opzione di ricerca approssimata. Prima e dopo la prova, Qdrant registra 11.032 punti e zero vettori indicizzati. Per stimare il richiamo di HNSW occorre ripetere il confronto dopo aver verificato la costruzione dell’indice.

\clearpage
## Dal motore al percorso del lettore

Il generatore k6 ha eseguito il percorso home, ricerca e apertura del primo articolo, verificando l’identità del documento e la presenza del testo. Il carico misto alternava E1 e ricerca semantica, con un tasso programmato di un percorso al secondo per 31 s. Generatore, applicazione ed encoder operavano sulla stessa macchina; Elasticsearch e Qdrant erano in container locali.

\tabletitle{percorso-web}{Percorso HTTP completo sotto carico misto locale}

| Misura | Valore osservato |
|:--|--:|
| Percorsi avviati e completati correttamente | 32 su 32 |
| Richieste HTTP / arrivi scartati dal generatore | 96 / 0 |
| Tempo del percorso, mediana | 32 ms |
| Tempo del percorso, P95 | 514 ms |

La Tab. \ref{tab:percorso-web} descrive un singolo livello di carico. Con soli 32 percorsi, il P95 dipende da poche osservazioni nella coda della distribuzione. La capacità sostenibile richiede più livelli di traffico e un generatore su un host separato.

**Tempo percepito nel browser.** In una singola osservazione Chromium sulla query «Roma», con E1, il primo risultato è diventato visibile 110 ms dopo l’invio. Dal clic sul risultato alla visualizzazione del testo dell’articolo sono trascorsi 748 ms. Sono due intervalli distinti della stessa navigazione; le 32 sessioni HTTP della tabella misurano invece il completamento delle richieste di rete.

I collaudi funzionali hanno inoltre verificato il filtro per anno e la seconda pagina dei risultati, la navigazione da una cartella dell’archivio a un articolo, la continuazione della ricerca live su risposte riprodotte localmente e la rilettura di un giudizio salvato in un database temporaneo.
