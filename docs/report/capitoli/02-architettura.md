\clearpage
# Architettura e responsabilità

Il browser offre tre punti di vista sullo stesso progetto. Il lettore cerca e consulta le notizie, il valutatore legge un articolo alla luce di un bisogno informativo e il coordinatore assegna il lavoro e chiude le revisioni. L’applicazione Python espone pagine HTML e API con FastAPI. I template Jinja costruiscono le pagine e JavaScript aggiorna risultati, filtri e moduli. I dati consultati cambiano con il compito.

La Fig. \ref{fig:componenti} mostra le dipendenze dei tre ambienti di lavoro.

\input{figure/architettura.tex}
\legendnote{componenti}{Dipendenze del servizio web. La richiesta determina il ramo da seguire. I due archivi SQLite hanno cicli di vita distinti: il catalogo del lettore si ricostruisce dal dump, i giudizi nascono dal lavoro dei valutatori.}

## Preparazione e interrogazione

La preparazione del corpus avviene da riga di comando. Leggere il dump, verificare i dati e costruire gli indici richiede accesso a file di grandi dimensioni. Al momento della ricerca questi lavori sono già conclusi. Il servizio riceve una richiesta breve, sceglie il percorso e restituisce una pagina di risultati. La distinzione permette di riavviare il sito senza ricostruire l’archivio e di valutare una nuova configurazione sullo stesso insieme di articoli.

\clearpage
## Identità, contratti e guasti

Il collegamento tra i componenti poggia su tre identificatori con scopi diversi. L’ID della pagina identifica l’articolo nell’archivio. La revisione stabilisce quale testo viene mostrato o giudicato. L’impronta del corpus identifica l’insieme completo su cui è stata costruita una configurazione. Un uguale numero di documenti, da solo, consentirebbe di confondere due raccolte con una pagina sostituita.

**Richiesta di ricerca.** L’API riceve testo, profilo e parametri di navigazione. Per l’archivio può applicare un intervallo di anni di pubblicazione. La risposta contiene elementi ordinati che la pagina presenta come schede. Il clic apre il dettaglio attraverso l’identificatore del documento. Mantenere i parametri nella navigazione permette al lettore di tornare alla ricerca e recuperare il contesto di partenza.

La Fig. \ref{fig:sequenza} segue una richiesta semantica dalla query alla risposta paginata.

\input{figure/query-semantica.tex}
\legendnote{sequenza}{Sequenza della ricerca semantica. Le linee continue indicano richieste, quelle tratteggiate le risposte. La selezione di un risultato avvia una richiesta distinta per aprire la revisione archiviata.}

**Contratto di annotazione.** Il pacchetto porta con sé i testi e i criteri del topic. Il database registra chi ha lavorato sulla coppia e quale versione del giudizio è stata salvata. Le citazioni puntano a intervalli del testo importato. Se una pagina su Wikimedia cambia durante la valutazione, quegli intervalli continuano a individuare il passaggio letto.

**Disponibilità.** La verifica di salute del backend controlla la connessione autenticata a Elasticsearch. Il controllo di prontezza richiede anche che gli indici previsti siano disponibili e coerenti. La postazione di annotazione dispone di un controllo separato. Questa distinzione aiuta a interpretare una pagina web raggiungibile che ancora non può restituire risultati: il processo può rispondere mentre manca un indice. Viceversa, un pacchetto già importato consente di proseguire le letture in SQLite anche durante un fermo del motore lessicale.
