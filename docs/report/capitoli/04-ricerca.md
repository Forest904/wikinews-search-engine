\clearpage
# Recupero lessicale

Per la query «incidenti ferroviari Giappone 2005», Elasticsearch cerca nei campi titolo e corpo. Un indice invertito consente di partire da un termine e raggiungere le pagine che lo contengono. Costruire due indici sugli stessi 11.032 documenti permette di variare l’analisi delle parole mantenendo fissi i testi. Un indice usa l’analizzatore standard, l’altro quello italiano.

La Fig. \ref{fig:lessicale} individua le fasi che determinano l’ordine dei risultati.

\flowrow{Testo e profilo\\della richiesta}{Analisi dei termini\\e clausole di ricerca}{Punteggio BM25\\e ordine dei risultati}
\legendnote{lessicale}{Percorso lessicale. Il profilo sceglie l’indice e le regole per interrogare titolo e corpo. A parità di punteggio decide l’ID del documento.}

BM25 combina l’importanza del termine nella raccolta con la frequenza nel documento. Una parola rara aiuta a distinguere le pagine; ripeterla molte volte dà un beneficio via via minore. La normalizzazione per lunghezza evita che un articolo esteso prevalga solo perché contiene più parole. I due indici usano gli stessi parametri, $k_1=1{,}2$ e $b=0{,}75$ [@bm25]. L’analizzatore italiano riduce varianti della stessa parola a forme confrontabili. Nel nostro esempio, questo rende meno rigida la distanza tra *ferroviari* e *ferroviario*.

Il motore combina titolo e corpo privilegiando il campo con la corrispondenza migliore. Con l’operatore OR anche una corrispondenza parziale può recuperare una pagina. La scelta favorisce la scoperta di candidati ma lascia al punteggio il compito di far emergere gli articoli centrali. Un anno esplicito nel filtro limita le date di pubblicazione. Nel benchmark Q37, invece, il vincolo del topic riguarda l’anno dell’incidente.

\clearpage
## Cinque modi di interrogare due indici

Le variazioni rispetto al profilo di base sono sintetizzate nella Tab. \ref{tab:profili}.

\tabletitle{profili}{Configurazioni lessicali confrontate sullo stesso corpus}

| Profilo | Indice | Differenza verificabile nella query |
|:---------|:----------|:----------------------------------------------|
| E0 | Standard | BM25 su titolo e corpo con uguale peso. |
| E1 | Italiano | Stessa query di E0, con analisi della lingua italiana. |
| E2 | Italiano | Il peso del titolo sale a 3. |
| E3 | Italiano | Alla base di E2 si aggiunge una corrispondenza tollerante ai refusi, con peso 0,2. |
| E4 | Italiano | Alla base di E2 si aggiunge la frase con peso 2. Le sequenze fra virgolette diventano obbligatorie. |

Il confronto E0–E1 isola l’effetto dell’analizzatore. E2 verifica l’ipotesi che il titolo riassuma l’argomento centrale. E3 ed E4 partono entrambi da E2. Per un refuso come *ferroviri* l’espansione di E3 può recuperare una forma simile: conserva il primo carattere e considera fino a 25 espansioni. E4 riconosce sia le virgolette dritte sia quelle tipografiche e segnala delimitatori vuoti o spaiati. Nelle query senza virgolette la frase può migliorare il punteggio.

### Latenza delle interrogazioni

La Tab. \ref{tab:latenza} confronta i tempi di risposta dei due profili.

\tabletitle{latenza}{Latenza HTTP nella seconda sessione locale, 40 richieste per profilo dopo il riscaldamento}

| Profilo | Mediana HTTP (ms) | 95º percentile (ms) |
|:--|--:|--:|
| E1 · italiano | 21,34 | 27,38 |
| E3 · refusi | 52,65 | 216,48 |

Il 95º percentile descrive la parte lenta delle risposte. Il costo delle espansioni emerge soprattutto lì. Questi tempi dipendono dalla macchina e dalle query impiegate; la qualità della classifica viene misurata separatamente.
