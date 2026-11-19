```{=latex}
\thispagestyle{empty}
\vspace*{12mm}
{\large Relazione tecnica e sperimentale\par}
\vspace{6mm}
{\LARGE\bfseries NewsFinder\par}
\vspace{2mm}
{\Large Architettura e valutazione di un motore di ricerca per Wikinotizie in italiano\par}
\vspace{8mm}

```

**Abstract.** Una notizia può essere pertinente anche quando il titolo usa parole diverse da quelle del lettore. Può anche condividere quasi tutte le parole della ricerca e descrivere un evento diverso. NewsFinder permette di osservare entrambi i fenomeni in un archivio di 11.032 articoli italiani. Il progetto comprende la preparazione dei dati, due percorsi di ricerca, un lettore web e una postazione con cui più valutatori giudicano i risultati sulla stessa revisione del testo.

Il confronto principale misura cinque configurazioni lessicali e una classifica esterna di Wikimedia. La configurazione scelta sui dati di sviluppo usa BM25 con analisi linguistica italiana. Su 16 bisogni informativi di test raggiunge 0,6558 in nDCG@10, una misura che premia i documenti pertinenti nelle prime posizioni. Solo 43 delle sue 160 posizioni esaminate hanno un giudizio umano. La copertura parziale dei giudizi limita l’interpretazione del confronto.

```{=latex}
\vfill
{\small\sffamily Sistemi di recupero dell’informazione \hfill 19 novembre 2026}

\clearpage
\tableofcontents
```

# Introduzione

«Incidenti ferroviari Giappone 2005» è la query del topic Q37. Il lettore cerca cronache di incidenti avvenuti in quel paese e in quell’anno. La data dei fatti può differire da quella di pubblicazione e il singolare *incidente* può esprimere lo stesso bisogno del plurale *incidenti*. Il caso collega tre scelte che altrimenti sembrerebbero indipendenti: quale testo conservare, come ordinarlo e quali prove chiedere a chi ne giudica la pertinenza.

Nel seguito il termine **documento** indica una pagina dell’archivio e la **revisione** identifica la versione del suo contenuto. Un **topic** comprende la domanda, i vincoli e i criteri per assegnare un giudizio. Questa distinzione consente di ripetere un confronto anche quando il sito pubblico cambia. Il riferimento per l’implementazione è la versione del repository indicata in bibliografia [@repo].
