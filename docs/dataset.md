# Corpus e ricerca

## Input e provenienza

Snapshot assegnato: **20 marzo 2025**, `itwikinews-NS0-20250320-ENTERPRISE-HTML.json.tar.gz`.
Fonte dichiarata dal progetto: [dump Wikimedia](https://dumps.wikimedia.org/other/enterprise_html/runs/20250320/itwikinews-NS0-20250320-ENTERPRISE-HTML.json.tar.gz).
La build locale usa la copia originale fornita dal maintainer, conservata in `data/raw/`.

| File | Byte | SHA-256 locale |
|---|---:|---|
| Archivio tar.gz | 72.975.193 | `d2c00ef9d7c3db5a3f26adb85b07055673b30b2417653374ada52b7174df474d` |
| `itwikinews_namespace_0_0.ndjson` | 591.305.405 | `26a48c1b40dbb693e98bf12877708d3867a538eef6a266038a40db61240505dd` |

Il membro dell'archivio coincide byte per byte con il NDJSON estratto. Questi hash
identificano le copie locali: non sono checksum certificati dal provider.

## Policy v1

Reader streaming e dedup su SQLite temporaneo. Una pagina corrisponde a un documento,
senza chunking. Si sceglie la revisione numericamente più alta, poi si richiedono
namespace 0, lingua italiana e categoria `Categoria:Pubblicati`. Si escludono URL
estranei a `https://it.wikinews.org/wiki/`, redirect effettivi, marcatori di cancellazione
immediata e corpo pulito vuoto. Il campo `redirects` descrive alias e non causa esclusione.

Revisioni identiche ripetute vengono collassate. Stessa pagina/revisione con payload
discordante costituisce errore bloccante. Schema invalido, JSON illeggibile, input
vuoto o archivio corrotto impediscono di certificare la build; l'audit produce log
anche per questi errori e restituisce exit code 1. Gli scarti previsti dalle policy
non costituiscono errori strutturali.

Il cleaner interpreta HTML con BeautifulSoup/lxml. Mantiene paragrafi, sottotitoli,
elenchi, citazioni, didascalie e celle delle tabelle informative in ordine di lettura.
Rimuove navigazione, script, stili, blocchi nascosti, avvisi e condivisione tramite
selettori strutturali. Sezioni Fonti/Note diventano metadati; articoli correlati,
collegamenti esterni e altri progetti sono esclusi dal corpo. Le sezioni successive
con contenuto giornalistico restano presenti. Spazi normalizzati e Unicode NFC.

Le date derivano dai parametri dei template Parsoid `Data` e `Luogodata`, prima
della pulizia. Solo una data valida e concorde viene salvata. Stati: `validated`,
`missing`, `invalid`, `ambiguous`; negli ultimi tre casi il valore è null.
`validated` significa validazione sintattica e concordanza del template editoriale,
non verifica storica indipendente. Nessun fallback a modifica, creazione, evento
o data della fonte. La mancanza di data non esclude un articolo.

## Contratto e artefatti

`ProcessedArticle` è separato dai modelli API M1 e contiene:

- `document_id`, `revision_id`: ID stringa; `title`, `body`, `url`.
- `categories`: nomi univoci ordinati; `publication_date`: ISO 8601 o null;
  `publication_date_status`, `publication_date_evidence`.
- `sources`: citazioni con `text` e `urls`, in ordine; `license`: metadati originali.
- `provenance`: `snapshot_id`, `input_sha256`, `member`, `line` (base 1).
  Fonti e data appartengono alla stessa revisione e ne ereditano la provenienza.

La build genera `articles.ndjson`, `manifest.json`, `audit.json`, `decisions.ndjson`.
Il manifest registra hash, versioni, conteggi, commit/stato Git, dipendenze e timestamp;
l'hash del sorgente della pipeline distingue anche modifiche locali non committate.
`destination_index` resta null in M2. L'audit non pubblica articoli.

Gli articoli sono ordinati per ID numerico e serializzati con chiavi ordinate, UTF-8
e newline LF. Due build dello stesso input devono essere identiche byte per byte.
Input tar.gz e NDJSON producono lo stesso contenuto al netto della provenienza,
che registra correttamente un hash diverso del contenitore. Timestamp e commit
sono metadati di esecuzione, non identità del corpus.

Le destinazioni popolate sono rifiutate. File e database intermedi vivono in una
directory temporanea; solo a successo vengono pubblicati con rename. Un errore non
sostituisce il corpus precedente. Non avviare due processi sulla stessa destinazione.

## Audit e limiti

L'audit iniziale riproduce 12.261 record, 12.213 pagine, 11.066 record con Pubblicati
e 11.032 pagine comparse almeno una volta nella categoria. Tutti i record osservati
hanno namespace 0 e lingua italiana. `date_created` compare solo in 242 record.

Gli esclusi senza Pubblicati includono speciali e aggregatori, ma anche titoli
plausibilmente giornalistici: la policy privilegia un criterio verificabile e può
ridurre la copertura. Non vengono aggiunte eccezioni silenziose.

Testi sotto 100 caratteri e sopra il percentile 99 sono segnalati, non eliminati.
Il campione deterministico usa ordinamento per SHA-256 dell'ID: 20 ammessi,
10 esclusi e 10 casi critici distinti, con priorità a tabelle, fonti, date incerte
e lunghezze estreme. La revisione non equivale a controllo manuale di tutto il dump.

La pulizia è a regole: template sconosciuti possono lasciare residui e tabelle
complesse perdono la disposizione bidimensionale. Date non riconosciute restano null.
Modifiche a questi criteri richiedono nuova versione e rigenerazione del corpus.

I dati raw/processed restano ignorati da Git. Si conservano URL, revisione e licenza
dichiarata dai record; il repository contiene solo fixture sintetiche. La licenza
del codice è distinta dai metadati di licenza dei contenuti.

Il [README](../README.md) contiene i comandi di acquisizione e indicizzazione.

Esiti per documento nella [revisione storica dei 40 casi](https://github.com/Forest904/wikinews-search-engine/blob/11577cdc898add969a5ab3ce9551f8cf8bdec511/docs/dataset-review.md). Il controllo
testuale assistito ha portato a rimuovere gli avvisi del template Notizia originale,
i rimandi standard ai calendari e i marcatori delle note, preservando i dati sportivi.
Restano possibili rimandi editoriali nella prosa e nomi file di immagini mancanti.

## Risultati verificati il 16 novembre 2026

Corpus finale locale: `data/processed/m2-v1/`. Seconda build indipendente:
`data/processed/m2-v1-repeat/`. Il pilot precedente resta in `data/processed/m2-pilot/`
e non deve essere usato per l'indicizzazione.

| Controllo | Esito |
|---|---:|
| Record letti | 12.261 |
| Revisioni superate | 48 |
| Pagine distinte | 12.213 |
| Esclusi senza Pubblicati | 1.181 |
| Articoli prodotti / ID univoci | 11.032 |
| Errori strutturali / conflitti / corpi vuoti | 0 |
| Data validated | 10.819 |
| Data ambiguous / invalid / missing | 130 / 2 / 81 |
| Articoli con fonti separate | 9.590 |
| Lunghezza minima / massima (caratteri) | 125 / 91.695 |
| Percentile 99 della lunghezza | 9.775 |
| Testi sotto 100 caratteri / sopra p99 | 0 / 110 |

Riconciliazione: **12.261 = 48 + 1.181 + 11.032**. Tutti gli articoli sono stati
rivalidati contro `ProcessedArticle`. Il campione finale coincide con i 40 ID
revisionati; i 30 corpi ammessi coincidono con quelli riesaminati dopo il pilot.
Nessuna occorrenza dei tre marcatori controllati di commenti, condivisione e
avviso Notizia originale nel corpus finale; non è una prova di assenza di ogni
possibile residuo editoriale.

Le due build hanno prodotto hash identici per tutti e tre gli artefatti deterministici:

| Artefatto | SHA-256 |
|---|---|
| `articles.ndjson` | `b85295e118431f71b06c56b04a27ca76010f90004eb45d29256ec8bca9443b45` |
| `audit.json` | `673f323d593e9fb0d9e6dff24882f5f5cd233cd3e3b5d2d27198505ec951df0a` |
| `decisions.ndjson` | `993ffcfde2e8a8f909bc2f5548f582e7d44ebf1039287e17f3a44241675834b9` |

Il manifest varia nei metadati di esecuzione. Equivalenza tar.gz/NDJSON verificata
su fixture sintetiche e identità del membro reale con il file estratto verificata
tramite SHA-256. Ruff superato; **72 test superati, 6 integration/E2E saltati** perché
non abilitati in questa verifica offline. I 22 test nuovi coprono la pipeline.
La CI remota non è stata eseguita in questa sessione. Evidenza locale aggiuntiva:
`output/m2-verification.json`.

## Attribuzione nella consegna

Per citare una notizia conservare il collegamento alla pagina originale, la revisione e la licenza indicata nel record. Wikinotizie indica CC BY per i testi dal 25 settembre 2005 e pubblico dominio per quelli precedenti salvo eccezioni. La pagina corrente rimanda a CC BY 4.0. Tutti gli 11.032 record del dump assegnato riportano invece CC-BY-SA-4.0 nel campo license. La pipeline conserva questa dichiarazione originale. Per redistribuire testi o immagini verificare la licenza e i crediti della singola revisione. La licenza software del repository riguarda il codice. [Copyright di Wikinotizie](https://it.wikinews.org/wiki/Wikinotizie:Copyright)

## Profili di ricerca

E0 usa BM25 con analyzer standard ed E1 con analyzer italiano. E2 aumenta il peso del titolo, E3 gestisce refusi e E4 aggiunge una clausola di frase. Gli ultimi tre condividono l’indice italiano. I sinonimi E5 furono rinviati per evitare espansioni prive di validazione. La UI espone il filtro temporale per le date supportate. Per configurazioni e pesi vedere i [profili versionati](../src/wikinews_ir/resources/retrieval/).

Il profilo semantico opzionale recupera vicini vettoriali con Qdrant ed embedding Ollama. La preparazione, la calibrazione e il ritorno alla collezione precedente sono descritti nelle [operazioni](operazioni.md#ricerca-semantica). La [roadmap](roadmap.md) descrive il futuro confronto con CirrusSearch.
