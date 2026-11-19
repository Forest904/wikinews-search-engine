# Relazione NewsFinder

Per leggere la relazione, apri il [PDF](newsfinder.pdf). Per aggiornarla, modifica i [capitoli Markdown](capitoli/) e rigenera il documento.

## Rigenerare il PDF

In VS Code modifica un capitolo Markdown, salvalo e scegli **Terminale → Esegui attività… → Report: rigenera PDF**. Il terminale dedicato mostra l’esito e il numero di pagine. Il file aggiornato è `docs/report/newsfinder.pdf`.

[Consulta il LaTeX generato](newsfinder.tex)

Dalla radice del repository eseguire `python docs/report/build.py`. Servono Python 3, Pandoc con citeproc, XeLaTeX e pdfinfo. Lo script usa latexmk quando disponibile e altrimenti esegue due passaggi di XeLaTeX. Servono i pacchetti LaTeX richiamati dal template, compresi Babel italiano, TikZ e xurl. Il PDF viene pubblicato solo dopo aver verificato il limite di 15–20 pagine.

I capitoli sono ordinati dal prefisso numerico. Il template e i disegni TikZ producono diagrammi vettoriali. Le quattro immagini PNG sono ritagli di schermate del collaudo browser, con dati dimostrativi. La bibliografia viene da `fonti.bib`. Per controllare visivamente una nuova impaginazione usare `pdftoppm -png docs/report/newsfinder.pdf docs/report/build/pagina`.

La figura sui componenti rispecchia le route dell’applicazione e i moduli reader, retrieval, annotation e semantic. La tabella del test viene generata da [test.tsv](figure/test.tsv), copia del riepilogo canonico della [release sperimentale](https://github.com/Forest904/wikinews-search-engine/releases/tag/v1.0.0). Per gli altri dati vedere [audit del corpus](../dataset.md), [latenze HTTP](../m4p-validation.md), [assegnazioni e giudizi](../m5d-validation.md) e [analisi delle classifiche](../m6b-validation.md). I dati della calibrazione semantica provengono dal file locale `experiments/reports/semantic-qwen3-06b.json`, prodotto con la [procedura di calibrazione](../semantic-search.md). La compilazione della relazione usa solo gli input presenti in questa directory.

La relazione adotta il formato A4 monocolonna. I richiami a figure e tabelle sono risolti da LaTeX. Pandoc applica il [file CSL IEEE](https://github.com/citation-style-language/styles/blob/master/ieee.csl) incluso nella directory. I riferimenti editoriali usati per la revisione sono il [manuale IEEE](https://journals.ieeeauthorcenter.ieee.org/wp-content/uploads/sites/7/IEEE-Editorial-Style-Manual-for-Authors.pdf), la [documentazione del progetto LaTeX](https://www.latex-project.org/help/documentation/) e la [Brochure SI del BIPM](https://www.bipm.org/en/publications/si-brochure).
