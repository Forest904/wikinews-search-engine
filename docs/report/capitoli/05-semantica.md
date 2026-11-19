\clearpage
# Recupero semantico

Una cronaca può descrivere un deragliamento senza usare l’espressione scelta dal lettore. Il percorso semantico rappresenta il testo con una sequenza di numeri, detta *vettore*. Ollama esegue il modello Qwen3 Embedding 0.6B; Qdrant confronta il vettore della query con quelli degli articoli usando la similarità coseno. Un punteggio alto esprime vicinanza secondo il modello. Verificare luogo, data e pertinenza resta un compito distinto.

La Fig. \ref{fig:vettori} distingue la preparazione del corpus dal calcolo eseguito per ciascuna domanda.

\flowrow{Preparazione\\Titolo e apertura}{Ollama\\Vettore del testo}{Pacchetto verificato\\Collezione Qdrant}
\flowrow{Ollama\\riceve la query}{Qdrant\\riceve il vettore}{Lettore d’archivio\\apre la revisione}
\legendnote{vettori}{Il percorso superiore prepara la raccolta una volta. Quello inferiore calcola il vettore della domanda a ogni ricerca e riapre il documento attraverso l’archivio.}

La Tab. \ref{tab:modello} descrive la rappresentazione vettoriale impiegata.

\tabletitle{modello}{Caratteristiche del pacchetto vettoriale completo}

| Proprietà del pacchetto completo | Valore |
|:--|--:|
| Documenti rappresentati | 11.032 |
| Dimensioni per vettore | 1.024 |
| Budget per il testo, incluso il token finale | 256 token |

Il programma risale all’HTML della revisione e rimuove elementi come figure e didascalie prima di comporre titolo e apertura. Conserva l’input esatto e conta i token con il vocabolario del modello. Questa scelta rende ispezionabile ciò che influenza un vettore. Il limite riguarda la copertura del testo: un luogo menzionato soltanto negli ultimi paragrafi può essere decisivo per chi legge e restare fuori dall’input semantico.

\clearpage
## Dal pacchetto alla ricerca verificabile

I vettori vengono scritti in lotti. Un’interruzione non obbliga a ripartire dal primo articolo e gli input identici possono essere riusati quando modello e runtime corrispondono. Il manifest lega i lotti al corpus e registra la configurazione dell’encoder. L’importazione crea una collezione, controlla i punti e aggiorna l’alias in un’unica operazione. Il lettore passa così a un insieme già verificato. La collezione precedente resta identificabile per il ripristino.

La Fig. \ref{fig:alias} mostra in quale momento una nuova collezione diventa disponibile.

\flowrow{Lotti e manifest\\con impronte}{Verifica di punti\\e revisione}{Cambio di alias\\alla collezione pronta}
\legendnote{alias}{Pubblicazione dei vettori. L’alias separa il nome usato dalle richieste web dalla collezione fisica in costruzione.}

### Una prova circoscritta

La Tab. \ref{tab:calibrazione} confronta i metodi sullo stesso insieme di candidati.

\tabletitle{calibrazione}{Calibrazione su quattro query e 24 candidati con giudizi silver}

| Metodo su 24 candidati | nDCG@10 media | Tempo mediano (s) |
|:--|--:|--:|
| BM25 italiano | 0,9522 | 0,039 |
| Vettori su testo naturale | 0,8183 | 15,468 |
| Vettori su termini ridotti alla radice | 0,8349 | 17,336 |
| Testo naturale, ricerca indicizzata | 0,8183 | 17,547 |

La media usa i casi con nDCG definita. Il profilo lessicale conserva le statistiche del corpus completo. La modalità esatta confronta i vettori direttamente, mentre quella indicizzata chiede a Qdrant una ricerca approssimata; su una raccolta così piccola il servizio può comunque scegliere una scansione completa. L’uguaglianza delle due medie sul testo naturale non stabilisce quale strategia convenga per 11.032 vettori. Servirebbe un confronto sul corpus intero, con giudizi e condizioni di misura comuni.
