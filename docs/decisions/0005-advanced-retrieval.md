# ADR 0005 — Retrieval avanzato M4

Data: 2026-11-16. Stato: implementato e verificato localmente.

## Decisione

E2, E3 ed E4 riutilizzano l'indice italiano M3 e lo stesso RetrievalEngine di
API, UI e run offline. Corpus, mapping, analyzer, E0/E1 e default E0 restano invariati.
Non servono nuovi indici. La build deduplica per famiglia, la readiness verifica
due indici fisici e restituisce cinque identità di profilo.

| Profilo | Comportamento v1 |
|---|---|
| E2 | best_fields, OR, title^3 e body^1 |
| E3 | E2 oppure fuzzy, somma dei contributi; fuzzy boost 0.2, AUTO:4,7, prefix_length 1, max_expansions 25, trasposizioni abilitate |
| E4 senza virgolette | E2 obbligatorio più phrase opzionale sull'intera query, boost 2, slop 0 |
| E4 con virgolette | Ogni frase obbligatoria; se presenti, termini esterni in una clausola OR obbligatoria |

E3 ed E4 sono ablation indipendenti di E2. Il peso fuzzy ridotto non garantisce
che qualsiasi corrispondenza esatta preceda qualsiasi corrispondenza fuzzy.
AUTO evita espansioni sui token molto brevi; prefix_length impedisce la correzione
del primo carattere. Anni e numeri non sono filtri temporali: il fuzzy può espanderli
e aumentare molto i candidati. Il profilo è sperimentale, non il nuovo default.

I boost sono configurabili nei YAML; cambiare un profilo richiede incremento
della sua versione e aggiornamento delle copie in resources e configs. Gli altri
parametri DSL sono fissati e validati per questa versione dell'implementazione.
Hash dei parametri e versione accompagnano risposte e manifest; il tag TREC deriva
dalla versione effettiva. Nessun tuning sul test gold.

## Frasi e validazione

Sono supportate coppie di virgolette dritte `"…"` e tipografiche `“…”`.
Apostrofi e punti interrogativi sono testo ordinario. Non sono introdotti operatori
booleani, wildcard o escape. Delimitatori spaiati, annidati o frasi vuote producono
ValueError/Pydantic ValidationError in Python, HTTP 422 nell'API e messaggi nella UI.
L'export valida tutte le query dei profili richiesti prima di interrogare il backend.
Le virgolette negli altri profili non hanno significato speciale.

Una frase deve corrispondere nel titolo oppure nel corpo, mai attraversando i campi.
`"energia solare" Italia Francia` richiede la frase e almeno uno dei due termini
esterni. Frasi multiple sono tutte obbligatorie e possono comparire in campi diversi.
Il match usa posizioni e analyzer italiano: stemming e stopword non equivalgono a
uguaglianza letterale. Frasi o clausole obbligatorie composte solo da stopword non
recuperano documenti; non viene mai inserito match_all come fallback.

## Highlight e compatibilità

SearchHit conserva title e snippet testuali; aggiunge title_segments e
snippet_segments, liste di `{text, highlighted}`. Lo snippet originale conserva
i primi 240 caratteri per compatibilità. La UI preferisce i segmenti del frammento
pertinente (circa 240 caratteri), altrimenti usa il testo originale.

Unified highlighter, encoder HTML e tag mark vengono convertiti in segmenti sul
server. Il browser usa soltanto textContent/nodi testuali e mark creati localmente;
non inserisce HTML ricevuto. Si analizzano al massimo 100.000 caratteri per campo
per l'highlight: corrispondenze successive possono non essere evidenziate, senza
limitare il retrieval. Un frammento non deve essere interpretato come prova di
tutti i vincoli della query: il vincolo resta nella DSL di ricerca.

L'export predefinito comprende E0–E4; `--profiles E0 E1` conserva l'export baseline.
Sort, score originali, atomicità e controlli d'identità rimangono invariati.

## Estensioni rinviate

E5 richiede dizionario, ipotesi e verifica di rumore dedicati: non necessario ai
Must M4. Il filtro date resta escluso per ambiguità/mancanze documentate in M2.
Nessuna correzione al cleaning viene introdotta sotto forma di modifica al ranking.

Evidenze: [verifica M4](../m4-validation.md). Riferimenti tecnici:
[multi-match](https://www.elastic.co/docs/reference/query-languages/query-dsl/query-dsl-multi-match-query),
[highlight settings](https://www.elastic.co/docs/reference/elasticsearch/rest-apis/highlighting-settings).
