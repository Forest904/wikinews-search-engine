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
