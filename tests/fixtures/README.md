# Articoli di esempio per i test

Usa la tabella per scegliere una query e controllare quale articolo dovrebbe comparire.

`articles.json` contiene cinque brevi testi inventati per lo scaffold del progetto,
già presenti in M0 e riutilizzati in M1. Non sono estratti dal dump né copie di
articoli Wikimedia; non costituiscono un benchmark di rilevanza.
Gli URL indicano soltanto la homepage Wikinotizie.

| ID stabile | Query dimostrativa | Titolo atteso |
|---|---|---|
| demo-01 | terremoto / soccorsi | Terremoto in Abruzzo |
| demo-02 | elezioni | Elezioni comunali |
| demo-03 | rinnovabili | Tecnologia e innovazione |
| demo-04 | calcio | Finale di calcio |
| demo-05 | museo | Cultura e musei |

`zzzznonpresente` non restituisce risultati. Il comando `seed-demo` valida i campi
obbligatori e l'unicità degli ID prima di scrivere. Il mapping standard usa BM25
e analyzer standard su titolo/corpo; `_id` coincide con `document_id`.
Caricare nuovamente il file sovrascrive gli stessi cinque ID senza duplicarli;
non elimina eventuali altri documenti già presenti nell'indice configurato.

Versione fixture: M1-v1. File JSON e mapping `configs/indices/standard.json` sono
versionati in Git: il commit identifica esattamente i contenuti della demo.
