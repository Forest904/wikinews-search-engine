# Dataset Wikinotizie — M2

## Percorso autonomo

Dalla radice della checkout, dopo `uv sync --locked`, eseguire
`uv run --locked wikinews-ir corpus prepare`. Default: archivio in `data/raw/`,
corpus in `data/processed/m2-v1/`. Opzioni: `--raw-dir DIR`, `--output DIR`.
URL, dimensione e checksum attesi sono fissati nel package ingestion; non occorrono
configurazioni esterne al wheel. Il riferimento SHA-256 resta quello locale
verificato, non un'attestazione pubblicata dal provider.

L'acquisizione usa HTTPS, User-Agent identificativo, timeout di connessione 15s
e timeout di inattività 60s. Sono previsti tre tentativi totali per errori di
trasporto, 429 e 5xx, con attese di 1 e 2 secondi. Nessun retry per altri errori
HTTP o checksum errato. Il download riparte dall'inizio; il temporaneo viene
rimosso anche in caso di interruzione e pubblicato solo dopo verifica.

Un archivio presente viene verificato e riusato offline. Se diverso dal riferimento,
il comando fallisce senza sostituirlo. Un corpus già popolato è riutilizzato solo
con manifest build valido, snapshot/checksum/versioni compatibili, stesso hash
del sorgente di preprocessing, stesse dipendenze e hash degli artefatti corretti.
Timestamp e stato Git non invalidano il riuso. Output incompleti o alterati richiedono
una nuova directory; nessuna sovrascrittura automatica. Non eseguire preparazioni
concorrenti sulle stesse directory.

Il comando aggiunge l'acquisizione davanti alla pipeline M2 senza cambiarne gli
articoli o il manifest. `corpus audit` e `corpus build` restano disponibili per
l'uso offline esplicito. Non sono previsti mirror o sostituzioni dello snapshot:
se Wikimedia non è disponibile, serve una copia locale corrispondente al checksum.

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

Comandi operativi nel [README](../README.md); motivazioni in [ADR 0003](decisions/0003-corpus-pipeline.md).

Esiti per documento nella [revisione del campione](dataset-review.md). Il controllo
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

## Collaudo dell'acquisizione autonoma

Il 16 novembre 2026 `corpus prepare` è stato eseguito su directory nuove
(`output/m2-acquisition/raw` e `output/m2-acquisition/processed`), scaricando
effettivamente l'archivio da Wikimedia. Il checksum coincide con il riferimento;
la build produce 11.032 articoli e gli stessi hash di `articles.ndjson`,
`audit.json` e `decisions.ndjson` riportati sopra.

La seconda esecuzione è stata verificata con client HTTP e funzione di build
disabilitati tramite mock: il comando verifica e riusa gli artefatti senza rete
né rielaborazione. Verificato anche il comando con i percorsi predefiniti.
Evidenza locale: `output/m2-acquisition/verification.json`.

Suite aggiornata: **93 test superati, 6 integration/E2E saltati**, Ruff superato.
I 21 test di acquisizione coprono HTTP simulato, retry, redirect HTTPS, checksum,
dimensioni, interruzioni, preservazione dei file e riuso offline. Nessun download
reale è richiesto in CI; la CI remota resta da verificare dopo il push.
