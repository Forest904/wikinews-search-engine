\clearpage
# Distribuzione e verifica

La Fig. \ref{fig:deploy} riassume il percorso di accesso al servizio distribuito.

\input{figure/distribuzione.tex}
\legendnote{deploy}{Distribuzione su server con Docker Compose. Caddy termina la connessione HTTPS. Il collegamento tratteggiato rappresenta il profilo semantico opzionale; il catalogo e il database dei giudizi sono disponibili su volumi montati. I lavori di preparazione e i backup seguono un ciclo distinto dalle richieste dei lettori.}

La configurazione locale separa dipendenze Python, credenziali e dati persistenti. Il comando di preparazione riusa un dump verificato; il comando di indicizzazione controlla il corpus prima di riutilizzare gli indici. Nel rilascio su server i test precedono la costruzione dell’immagine Linux, trasferita via SSH. Caddy gestisce l’ingresso HTTPS. Il database di annotazione richiede un backup dedicato: ricostruire gli indici dal dump recupera il testo, ma i giudizi umani esistono soltanto se si conserva il database o il relativo export.

La Tab. \ref{tab:verifiche} associa ogni livello di verifica a una proprietà osservabile.

\tabletitle{verifiche}{Controlli del servizio e proprietà verificate}

| Livello di verifica | Esempio di proprietà controllata |
|:--|:--|
| Unitario | Una query con virgolette spaiate viene respinta; una revisione conflittuale impedisce di certificare il corpus. |
| Integrazione | Le query raggiungono Elasticsearch e gli indici previsti rispondono sul corpus preparato. |
| Browser | Aprire un articolo e tornare ai risultati conserva la ricerca; le postazioni permettono di completare il lavoro assegnato. |
| Ripetizione sperimentale | Le classifiche di otto query di controllo coincidono prima e dopo la ricostruzione degli indici. |

\clearpage
# Conclusioni

Su Q37 E1 porta ai primi due posti due cronache di grado 2; su Q09 un articolo di grado 2 scende al secondo posto. Sui 16 topic il vantaggio medio di E1 sul semantico è di 0,0591 in nDCG@10. L’intervallo appaiato comprende lo zero. Giudicare i risultati semantici ancora scoperti renderebbe il confronto più informativo. Restano da misurare il richiamo con indice HNSW attivo e la capacità web su replica con generatore separato.

## Fonti e riproducibilità

La descrizione iniziale del servizio si riferisce alla revisione \texttt{8fe85c8}, i risultati congelati alla \texttt{1c6e51d}. La release pubblica contiene classifiche, giudizi e manifest SHA-256. Per le successive campagne locali, il file \texttt{benchmark-locale.json} raccoglie gli identificativi delle esecuzioni, i denominatori e le statistiche delle tabelle.

**Riprodurre il servizio.** La procedura documentata avvia Elasticsearch con Docker Compose, verifica il dump e prepara gli indici per FastAPI. Il recupero semantico richiede anche encoder e collezione vettoriale. Le postazioni di giudizio richiedono un account e un pacchetto importato.

**Nota sulle immagini.** I diagrammi rappresentano i percorsi del codice. I ritagli delle interfacce provengono dal collaudo con dati dimostrativi. L’esempio documentale deriva dalla revisione di Wikinotizie indicata fra le fonti, distribuita con licenza [Creative Commons Attribuzione-Condividi allo stesso modo 4.0](https://creativecommons.org/licenses/by-sa/4.0/).

## Riferimenti

::: {#refs}
:::
