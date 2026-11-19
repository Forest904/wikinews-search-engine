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

Siamo partiti da una ricerca sugli incidenti ferroviari in Giappone. Su Q37 l’analizzatore italiano porta ai primi due posti due cronache di grado 2. Su Q09, con lo stesso analizzatore, un articolo di grado 2 scende dal primo al secondo posto. Abbiamo scelto E1 sulla base del risultato medio di sviluppo. I due casi di test ci aiutano a capire come quella scelta cambia ciò che il lettore trova per primo. Per decidere se estendere la preferenza al recupero semantico, il passo sperimentale più informativo sarebbe giudicare anche i suoi primi risultati sullo stesso insieme di topic. L’architettura consente questo confronto; la copertura osservata quantifica il lavoro di annotazione ancora necessario.

## Fonti e riproducibilità

Il codice descritto corrisponde alla revisione \texttt{8fe85c8} del repository. I risultati congelati si riferiscono alla revisione sperimentale \texttt{1c6e51d}. La release pubblica riunisce classifiche, giudizi e risultati. Per verificare i numeri si confrontano prima le impronte SHA-256 con il manifest archiviato, poi si ricostruiscono le medie per sistema mantenendo fonte, profondità e insieme dei topic. La tabella del test è generata dal riepilogo tabulare originale.

**Riprodurre il servizio.** Con Python 3.12 e le dipendenze fissate nel lockfile, la sequenza comprende l’avvio di Elasticsearch tramite Docker Compose, la preparazione del corpus, la costruzione degli indici e l’avvio dell’applicazione FastAPI. La componente semantica richiede anche il modello e la collezione vettoriale. La postazione di giudizio richiede un account e un pacchetto importato. I comandi completi e i prerequisiti sono nella documentazione associata alla revisione del progetto.

**Nota sulle immagini.** I diagrammi rappresentano i percorsi del codice. I ritagli delle interfacce provengono dal collaudo con dati dimostrativi. L’esempio documentale deriva dalla revisione di Wikinotizie indicata fra le fonti, distribuita con licenza [Creative Commons Attribuzione-Condividi allo stesso modo 4.0](https://creativecommons.org/licenses/by-sa/4.0/).

## Riferimenti

::: {#refs}
:::
