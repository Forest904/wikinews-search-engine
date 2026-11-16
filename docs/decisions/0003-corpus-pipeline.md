# ADR 0003 — Corpus offline e policy M2

## Estensione: acquisizione autonoma

`corpus prepare` orchestra download HTTPS e `run_corpus`. Riferimento URL, byte e
SHA-256 fissato nel package, User-Agent esplicito, streaming in temporaneo e rename
dopo verifica. Un file locale differente non viene sovrascritto. Retry limitati
a errori temporanei; nessun mirror o cambio snapshot implicito.

Il riuso è verificato: archivio atteso, manifest compatibile, dipendenze e hash
degli output corretti. Una riesecuzione con archivio e corpus validi non usa rete
né rielabora. La pipeline e i suoi output deterministici restano invariati.

Data: 2026-11-16. Stato: accettato.

## Contesto

Lo snapshot Enterprise contiene revisioni multiple, HTML editoriale e date con
significati differenti. M2 fissa identità e testo prima di indicizzazione e benchmark.
L'archivio locale contiene un NDJSON identico alla copia estratta fornita.

## Decisioni

- Reader streaming tar.gz/NDJSON e SQLite temporaneo per revisioni e dedup, senza
  estrarre percorsi dell'archivio sul filesystem.
- Revisione con ID numerico massimo, poi ammissibilità: namespace 0, italiano,
  Pubblicati, URL Wikinotizie valido, nessun redirect o marcatore di cancellazione
  immediata, corpo non vuoto. Nessuna eccezione per pagine senza Pubblicati.
- Preservare testo e tabelle informative; separare Fonti/Note dal corpo. Rimuovere
  blocchi editoriali e navigazione per struttura, non tutti i template o le tabelle.
- Date solo dai template Parsoid Data/Luogodata, con evidenza; nessuna inferenza da
  data di modifica, evento o citazioni. Conflitti e valori invalidi danno null.
- `ProcessedArticle` è un contratto offline distinto dall'API M1. M3 implementerà
  il caricamento negli indici; M2 non modifica Elasticsearch.
- Errori di schema, archivio o conflitti della stessa revisione bloccano la build.
  L'audit esporta diagnostica e restituisce esito negativo.
- Directory temporanea e rename finale; destinazioni popolate rifiutate.

## Conseguenze

Escludere pagine senza Pubblicati può perdere notizie autentiche. Il limite è
documentato e misurabile, senza ampliare silenziosamente il corpus.

Serializzazione UTF-8 canonica, ordinamento numerico, policy versionate e checksum
identificano il corpus. Timestamp e stato Git sono metadati di esecuzione.
Archivio e NDJSON producono lo stesso contenuto semantico; la provenienza differisce
per checksum del contenitore e posizione. Ripetizioni dello stesso input devono
produrre articoli identici byte per byte.

I checksum locali non attestano autenticità rispetto a un checksum del provider.
La licenza dichiarata dai record è conservata; i test sono sintetici e il repository
non redistribuisce gli articoli.

## Verifica

Test offline nella CI esistente, build reale e revisione di 40 pagine.
Conteggi, checksum finali, campione e limiti in [dataset.md](../dataset.md).
