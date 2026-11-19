\clearpage
# Metodo di valutazione

Per Q37, nominare il Giappone è insufficiente. Il topic richiede un incidente ferroviario avvenuto nel 2005. Il valutatore legge il testo completo usando una rubrica a tre livelli: 2 per una trattazione centrale e sostanziale, 1 per informazioni concrete ma secondarie, 0 se il bisogno resta insoddisfatto. Un vincolo essenziale incerto può motivare una richiesta di revisione. Assegnare 1 per esprimere incertezza confonderebbe due situazioni diverse.

La Fig. \ref{fig:pool} ricostruisce la selezione delle coppie sottoposte a giudizio.

\flowrow{Topic e criteri\\congelati}{Classifiche riunite\\e coppie distinte}{Letture assegnate\\e giudizi finali}
\legendnote{pool}{Costruzione del pool. Le classifiche di più sistemi propongono candidati. L’unità di giudizio è la coppia fra un topic e un documento.}

La Tab. \ref{tab:assegnazioni} distingue le letture assegnate dalle coppie distinte.

\tabletitle{assegnazioni}{Copertura del giudizio umano e carico di lettura per insieme di topic}

| Raccolta | Topic | Coppie nel pool | Con giudizio umano | Letture assegnate |
|:--|--:|--:|--:|--:|
| Sviluppo | 24 | 595 | 116 | 139 |
| Test | 16 | 387 | 74 | 89 |
| Totale | 40 | 982 | 190 | 228 |

La calibrazione iniziale permette di provare istruzioni, confrontare interpretazioni e misurare il tempo richiesto prima di fissare il carico dei valutatori. Le letture superano le coppie umane perché alcune vengono assegnate due volte. Tra le 38 doppie letture, 30 producono lo stesso grado e otto differiscono di un livello. Un terzo valutatore risolve questi otto casi; una nona revisione chiude una richiesta relativa a una lettura singola. La decisione finale si affianca alla storia dei giudizi individuali.

\clearpage
## Tracciabilità dei giudizi

La Fig. \ref{fig:postazioni} illustra la ripartizione dei compiti fra valutatore e coordinatore.

\shot{giudizio}
\shot{coord}
\legendnote{postazioni}{Postazioni di collaudo. Chi valuta affianca testo e grado; chi coordina prepara il blocco di assegnazioni per un topic.}

Il valutatore seleziona un passaggio, lo associa al giudizio e ne motiva il grado. Il sistema conserva campo, citazione e posizioni iniziale e finale. Controllare questi riferimenti consente di ritrovare l’evidenza nella stessa revisione. I salvataggi sono versionati: un tentativo ripetuto non deve creare una seconda decisione e una bozza obsoleta non deve cancellare il lavoro successivo.

Il coordinatore assegna blocchi e doppie letture, segue le richieste di revisione ed esporta i giudizi finali. Le *qrels* associano topic, documento e grado. Il riferimento umano, detto *gold*, copre 190 coppie. Un secondo processo, svolto senza mostrare al modello classifiche e gold, produce giudizi *silver* per tutte le 982 coppie. Sulle 74 coppie condivise del test il confronto dà macro-F1 pari a 0,8357 e kappa con pesi lineari pari a 0,8803. Nei sei disaccordi il silver assegna sempre il grado inferiore. L’ampliamento della copertura porta dunque anche una diversa fonte di errore.
