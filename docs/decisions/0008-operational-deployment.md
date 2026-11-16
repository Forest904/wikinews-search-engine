# ADR 0008 — Pubblicazione temporanea su Hetzner e Cloudflare

Data: 2026-11-16. Decisione concordata; collaudo online pendente.

Una VPS Ubuntu x86 da 4 GB ospita Caddy, FastAPI e Elasticsearch in Docker,
per circa due mesi e circa 10 €/mese, subordinati al preventivo effettivo.
Cloudflare gestisce DNS/proxy di newsfinder.win e TLS Full (strict).
Solo Caddy è esposto; Elasticsearch è in rete privata. SQLite resta il database
locale persistente: il carico di tre annotatori non giustifica una migrazione
PostgreSQL in M7-A. La tenuta dei 4 GB resta da misurare sulla VPS.

L'utente ha escluso backup sul server e S3 e accettato copie manuali sul PC.
Lo snapshot SQLite viene prodotto in RAM e trasmesso via SSH, senza archivio
di backup persistente sulla VPS. Una copia PC e un ripristino locale verificato
sono il gate aggiornato; nessuna automazione di backup o RPO garantito.
Al termine si esportano gli artefatti scientifici prima di eliminare il server.

Health applicativo e annotazione sono separati dalla disponibilità della ricerca.
Il deployment usa commit e tag immagine identificabili, senza cancellare volumi.
M7-A non certifica il benchmark: nessuna verifica locale sostituisce accesso da
computer distinti, collaudo concorrente e misura risorse online.

Procedura operativa fornita in chat. Evidenze: [M7-A](../m7a-validation.md).
