# ADR 0006 — Annotazione collaborativa M5-B

Data: 2026-11-16. Stato: accettata e implementata localmente.

## Contesto

M5-A dispone di pacchetti congelati e contratti dei giudizi. Tre validatori devono
annotare indipendentemente, riprendere il lavoro e risolvere i disaccordi, prima
della pubblicazione M7-A e del pilot M5-C. Il coordinatore è anche un validatore.

## Decisioni

- Integrare UI Jinja/JavaScript e API nell'app FastAPI esistente, con moduli di
  storage, workflow, export e amministrazione separati dal retrieval.
- Usare SQLite locale persistente, WAL, transazioni `BEGIN IMMEDIATE`, schema
  versionato e connessioni chiuse al termine di ogni richiesta. Un solo server è
  sufficiente per il budget attuale; replica e PostgreSQL non sono requisiti M5-B.
- Creare account da CLI, password scrypt e sessioni lato server revocabili, CSRF,
  controllo origine, limite login e cookie Secure configurabile per M7-A.
- Importare il contenuto verificato dei pacchetti, rendendolo indipendente dai
  percorsi originali, dagli indici e da servizi esterni.
- Preparare blocchi per topic e attivarli dopo il riepilogo. Assegnazioni e quota
  doppia si congelano all'attivazione; ordine e campionamento derivano da seed e hash.
- Restituire agli annotatori solo attività assegnate e giudizi propri. Mostrare
  originali altrui esclusivamente nella revisione assegnata a un utente indipendente.
- Finalizzare automaticamente singoli e accordi completi. Per dubbi/disaccordi
  assegnare un revisore esterno agli autori. Le finali restano separate dagli originali.
- Versionare ogni salvataggio e invalidare atomicamente le finali superate.
  Combinare versione attesa e chiave di idempotenza per conflitti e retry.
- Riutilizzare `Judgment` e l'export M5-A senza cambiarne la semantica. Le finali
  automatiche sono derivate da giudizi umani, con identificativo di sistema e
  provenienza esplicita; non sono giudizi LLM né attribuite a una persona fittizia.
- Esportare per split solo coppie consolidate nei qrels, allegando lo storico
  separato. Richiedere rilascio esplicito del test e registrarlo nell'audit.

## UI e conseguenze

La UI desktop affianca criteri, documento e modulo. La versione mobile impila le
sezioni e offre navigazione rapida. Evidenziazione e scorciatoie agevolano la lettura,
senza suggerire il grado. I salvataggi falliti mantengono il form; l'avanzamento
richiede conferma del server. Le citazioni convertono gli offset UTF-16 del browser
in punti di codice Unicode e vengono ricontrollate sul server.

I blocchi attivi non si modificano; variazioni del disegno di raccolta richiedono
un nuovo pacchetto. L'accesso amministrativo al filesystem e l'export del coordinatore
sono privilegi fidati, non una sandbox contro il responsabile del benchmark.
Il test non viene collegato a strumenti di tuning.

La pubblicazione HTTPS, la strategia di backup remoto e le verifiche tra computer
rimangono M7-A. Le fixture certificano il funzionamento, non la validità sperimentale
dei giudizi. Evidenze in [m5b-validation.md](../m5b-validation.md).
