\clearpage
# Dal dump all’archivio

Lo snapshot Wikimedia Enterprise HTML del 20 marzo 2025 contiene pagine del namespace principale di Wikinotizie in italiano. Il file compresso occupa circa 73 MB e il suo membro NDJSON circa 591 MB. Il formato dispone un record JSON su ogni riga. Il programma può quindi leggere in sequenza e usare un database SQLite temporaneo per confrontare le revisioni, senza mantenere in memoria l’intero archivio.

I conteggi della Fig. \ref{fig:selezione} consentono di riconciliare le pagine ammesse con i record iniziali.

\flowrow{12.261 record\\nel dump}{12.213 pagine\\distinte}{11.032 articoli\\nel corpus}
\legendnote{selezione}{La selezione elimina 48 revisioni superate e 1.181 pagine prive della categoria editoriale richiesta. I conteggi si riconciliano con l’intero input.}

Per ogni pagina si sceglie la revisione con identificatore numerico più alto. Si controllano lingua, namespace, URL e presenza della categoria *Pubblicati*. Redirect effettivi, corpi vuoti e marcatori di cancellazione hanno regole esplicite. Un record illeggibile o due contenuti discordanti per la stessa revisione bloccano la certificazione. La categoria è un criterio osservabile, ma può lasciare fuori pagine dal titolo giornalistico prive di quel marcatore.

Il pulitore conserva paragrafi, sottotitoli, elenchi, didascalie e celle informative; separa le fonti dalla prosa e rimuove navigazione, avvisi e collegamenti di servizio. La data editoriale proviene dai template della revisione. Quando le date sono discordanti abbiamo lasciato il campo vuoto. Usare la data dell’ultima modifica avrebbe potuto far comparire una cronaca nell’anno della sua revisione.

Gli esiti della validazione temporale sono riportati nella Tab. \ref{tab:date}.

\tabletitle{date}{Validazione della data editoriale negli 11.032 articoli}

| Data editoriale nel corpus | Articoli | Effetto sul filtro per anno |
|:-----------------------|----------:|:---------------------------------|
| Valida e concorde | 10.819 | L’anno è confrontabile con l’intervallo richiesto. |
| Ambigua | 130 | Il valore resta nullo. |
| Invalida | 2 | Il valore resta nullo. |
| Assente | 81 | Il valore resta nullo. |

\clearpage
## Provenienza di una revisione

Per Q37 si può seguire il documento 1374, *Incidente ferroviario in Giappone*. Il suo titolo è al singolare. L’apertura colloca l’incidente tra Osaka e Kobe e il testo riporta il 25 aprile 2005. L’articolo offre quindi più elementi per giudicare il bisogno informativo di quanti ne renda visibili la sola corrispondenza fra titolo e query [@wiki].

La Fig. \ref{fig:revisione} collega il record elaborato alla revisione utilizzata per il giudizio.

\branchrow{Sorgente}{Snapshot del 20 marzo 2025, riga 4.427 del membro NDJSON. Pagina 1374, revisione 100252.}
\branchrow{Testo editoriale}{Titolo e corpo restano campi distinti. Il corpo conserva l’apertura «25 aprile 2005» e la cronaca.}
\branchrow{Record elaborato}{Data di pubblicazione 2005-04-25, tre fonti separate, URL originale, licenza CC BY-SA 4.0 e provenienza.}
\legendnote{revisione}{Lettura guidata di un record reale. La riga individua il materiale sorgente e la revisione consente di riaprire la versione citata.}

### Come si controlla la trasformazione

La build pubblica gli articoli ordinati per ID, un registro delle decisioni, un audit e un manifest con hash e versioni. Su due preparazioni indipendenti coincidono byte per byte articoli, registro e audit. Le date di esecuzione appartengono al manifest. L’identità dell’output rende verificabile la ripetizione del processo, mentre l’esame dei testi misura un’altra proprietà: quanto bene le regole preservano il contenuto giornalistico.

La revisione manuale campiona 40 casi tra ammessi, esclusi e critici. Tabelle lunghe, date incerte e articoli molto estesi meritano attenzione perché una trasformazione può essere deterministica e perdere comunque informazioni. Per esempio, leggere le celle nell’ordine corretto conserva il testo di una classifica sportiva, ma può rendere meno evidente il rapporto visivo fra intestazioni e colonne.
