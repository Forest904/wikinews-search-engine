# Collaudo della consegna tecnica · 19 novembre 2026

## Installazione sul PC della demo

Clone Git pulito del commit sperimentale `1c6e51d`, Python 3.12.2, uv 0.12.9, Docker Engine 29.4.3, Compose 5.1.3. Il PC Windows dispone di 31,3 GiB di RAM e 16 processori logici. Il collaudo ha usato una configurazione generata da .env.example, credenziali locali nuove, una porta libera e un volume Elasticsearch vuoto nel progetto Compose dedicato `wikinews-m7b-check`.

L’unico input del corso copiato nel clone è il tar.gz originale di 72.975.193 byte. Il controllo SHA-256 integrato lo ha accettato. La verifica HTTP HEAD dell’URL storico ha restituito 403. La copia offline è stata necessaria per provare in modo indipendente preprocessing e indicizzazione.

| Verifica | Esito osservato |
|---|---|
| Installazione bloccata da uv.lock | Ambiente Python nuovo e 55 pacchetti installati |
| Corpus reale | 12.261 record letti, 48 revisioni superate, 1.181 pagine escluse, 11.032 articoli |
| Indici Elasticsearch 9.5.6 | 11.032 documenti per indice. Prima build in 8,3 s per standard e 6,2 s per italiano |
| Risorse | Circa 5 min 35 s dal clone alla fine dell’indicizzazione, cache locali già presenti. Checkout e ambiente circa 534 MB, volume Docker circa 128 MB. Durante il preprocessing osservato un file temporaneo di 537 MB |
| Qualità | Ruff superato. Suite ordinaria 223 passati, 28 test subordinati a servizi esclusi dalla prima esecuzione. Eseguiti separatamente sul cluster isolato con Chromium: 18 test di integrazione e UI, 10 test browser di annotazione. Totale 251 passati |

## Demo e recupero

Dopo arresto e riavvio del container dedicato, la readiness ha confermato lo stesso corpus e gli stessi UUID per entrambi gli indici. Health HTTP 200. Una nuova istanza FastAPI e un browser Chromium hanno eseguito la [scaletta della demo](demo.md) con richieste browser e connessioni dell’applicazione limitate a loopback. La scheda di rete del PC è rimasta attiva.

Le ricerche di confronto hanno restituito rispettivamente 1.538 e 1.928 risultati. Il dettaglio del primo articolo E1 e il ritorno ai risultati hanno funzionato. Il filtro 2005 ha restituito 20 risultati con date corrette nella prima pagina. Il refuso con E3 ha restituito 7.955 risultati. La query senza corrispondenze ha mostrato lo stato vuoto.

## Evidenze scientifiche e verifiche residue

Controllati tutti i 39 SHA-256 del manifest M6-B. Ricostruite le medie gold di entrambi gli split dai file per topic, applicando MRR ai soli topic evento. L’allegato della release contiene 49 file, inclusi manifest, run e qrels. SHA-256 dello ZIP: `c8b16318b31d145883b275a54a2d6e93fbe979f6c39fa9643fd829846d2fa967`. Il pacchetto esclude dump, indici e materiali individuali di annotazione.

Presentazione, PDF e prova orale rinviati su richiesta. La prova della demo sulla rete effettiva dell’aula rimane aperta. [Risultati e limiti del benchmark](../m6b-validation.md)
