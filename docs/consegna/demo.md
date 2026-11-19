# Demo live su questo PC

Prima della lezione completare il setup del README, verificare entrambi gli indici e lasciare Elasticsearch e FastAPI avviati. Aprire la home su http://127.0.0.1:8000/. Le modalità lessicali e il dettaglio locale funzionano con la rete esterna indisponibile.

| Query | Azione nella UI | Cosa osservare |
|---|---|---|
| incidenti ferroviari Giappone 2005 | Aprire Filtri, scegliere Standard, cercare. Ripetere con Analisi italiana. | Confrontare i primi titoli a parità di query. E0 inizia con 21736 e 27073, E1 con 1374 e 2273. Con E1 aprire il primo articolo e tornare ai risultati. |
| Giappone | Scegliere Analisi italiana e impostare entrambi gli anni a 2005. | Attesi 20 risultati. Controllare la data di pubblicazione degli articoli. Il filtro opera sulla data editoriale. |
| incidenti ferroviri Giappone 2005 | Svuotare i campi anno e scegliere Tolleranza ai refusi. | Il primo risultato della variante con refuso è 1374. |
| zzzqxwvkmn | Scegliere Standard e cercare. | Mostrare lo stato vuoto e tornare alla ricerca precedente. |

## Ripristino rapido

Controllare `/api/health`, poi `/api/ready`. Se Elasticsearch è fermo, dalla directory del progetto usare `docker compose up -d --wait elasticsearch`. Se risponde ma gli indici mancano, eseguire `uv run --locked wikinews-ir index build` sul corpus verificato. Per riavviare il servizio web usare `uv run --locked uvicorn wikinews_ir.api.main:app`. Conservare il volume Elasticsearch. Per il ripristino in aula usare la stessa directory, lo stesso progetto Compose e la stessa configurazione del collaudo.
