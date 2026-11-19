\clearpage
# Dalla pagina dei risultati alla lettura

Una scheda utile deve aiutare a decidere se vale la pena aprire l’articolo. NewsFinder mostra titolo e anteprima e permette di evidenziare le corrispondenze. Nelle schermate di collaudo la domanda riguarda l’energia. Il titolo «Energia solare, inaugurato il nuovo centro di ricerca» passa dalla lista al lettore: la continuità del titolo rende riconoscibile la pagina scelta. I contenuti dimostrativi servono qui a leggere i controlli dell’interfaccia.

La Fig. \ref{fig:lettore} documenta il passaggio dalla selezione del risultato alla lettura.

\shot{risultati}
\shot{lettore}
\legendnote{lettore}{Due ritagli della stessa sessione dimostrativa. In alto si sceglie una notizia dalla classifica, in basso si ritrova il titolo e si legge il testo.}

Le opzioni di ricerca riuniscono modalità e periodo. Nell’archivio il lettore può anche navigare per argomenti e aprire i salvati. Il sito conserva nel browser i riferimenti salvati e le ricerche recenti. La disponibilità in una successiva visita dipende quindi dal browser utilizzato. Il ritorno ai risultati conserva query e pagina, particolarmente utile quando si confrontano più resoconti dello stesso evento.

\clearpage
## Archivio, articolo e fonte aggiornata

La Fig. \ref{fig:percorsi} distingue i percorsi di accesso alle fonti.

\branchrow{Esplorazione}{Home o cartella tematica → elenco di articoli → lettore della revisione archiviata.}
\branchrow{Ricerca filtrata}{Query e intervallo di anni → risultati dell’archivio → ritorno alla stessa ricerca.}
\branchrow{Consultazione live}{Ricerca su Wikimedia → risultati del servizio esterno → pagina della fonte.}
\legendnote{percorsi}{I percorsi disponibili al lettore. La scelta della fonte determina se il risultato appartiene allo snapshot o al sito aggiornato.}

Nell’archivio, un intervallo di anni riconosciuto nella casella di ricerca può alimentare i campi del periodo. Il lettore può controllarli e modificarli. La selezione riguarda la pubblicazione: per Q37 un articolo commemorativo uscito nel 2015 potrebbe parlare proprio dell’incidente del 2005. Se limitiamo il filtro al 2005 lo escludiamo a monte, prima ancora di valutarne il contenuto. Per questo il testo della domanda sperimentale e i parametri effettivi della richiesta vanno conservati insieme.

Il lettore rende consultabili testo e informazioni editoriali. Blocchi strutturati e immagini, quando disponibili, migliorano la lettura di notizie lunghe; il collegamento alla fonte permette di proseguire sul sito originale. Le evidenze dei valutatori restano ancorate al testo congelato, anche se la presentazione pubblica dispone di una resa più ricca.

Un articolo può avere molte categorie editoriali. Per presentarlo in cartelle, il sistema assegna la corrispondenza più profonda nella gerarchia e usa una priorità prestabilita in caso di parità. Per esempio, una pagina con categorie Sport, Calcio e Serie A compare nel ramo più specifico. Il lettore strutturato usa invece un catalogo SQLite ricavato dalla revisione HTML: conserva tabelle, citazioni e collegamenti interni verso gli articoli disponibili. Le immagini riportano i crediti e la licenza quando questi dati soddisfano i controlli previsti.

Un elenco vuoto ha un significato preciso solo quando la ricerca è riuscita. La pagina comunica separatamente un errore del servizio e l’assenza di corrispondenze. Questa distinzione conta anche nell’uso quotidiano: nel primo caso ripetere la richiesta può avere senso, nel secondo cambiare termini o ampliare il periodo modifica davvero l’insieme dei candidati.
