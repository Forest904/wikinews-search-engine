# M7-A — Implementazione e verifiche

**18 novembre 2026 — Sito pubblicato.** Verifica HTTPS sul dominio pubblico:

| Endpoint | HTTP | Risposta |
|---|---:|---|
| `https://newsfinder.win/api/health` | 200 | `{"app":"ok","elasticsearch":"ready"}` |
| `https://newsfinder.win/api/health/annotation` | 200 | `{"annotation":"ready"}` |

Il precedente HTTP 503 della ricerca è superato. Le prove operative svolte direttamente dal coordinatore, tra cui accessi individuali e ripristino della copia PC, attendono conferma per chiudere il gate.

## Stato iniziale del 16 novembre 2026

Disponibili Compose produzione, Caddy, bootstrap Ubuntu, deploy per commit,
health separati, log degli errori di scrittura senza payload e copia SQLite
via SSH direttamente sul PC. Nessun account cloud, DNS o server è stato modificato.
La configurazione usa SQLite e nessuno storage di backup sul server, come
concordato in [ADR 0008](decisions/0008-operational-deployment.md).

## Evidenze locali

- Ruff: superato.
- Suite predefinita: 174 passati, 16 saltati (integration/browser opt-in).
- Nuovi test: probe senza creazione/migrazione implicita, schema incompatibile,
  snapshot con dati WAL e audit, trasferimento verificato, destinazione esistente,
  trasferimento interrotto senza pubblicazione del file finale.
- Compose produzione: `config --quiet` superato con valori di prova.
- Script server: sintassi Bash verificata in container Bash 5.2.
- Caddy 2.10.2: configurazione validata con certificato locale temporaneo.
  Non è una verifica del certificato Cloudflare o del dominio online.
- Warning preesistente Starlette/httpx nei test; non blocca la suite.
- Browser annotazione: 3 test passati con `RUN_ANNOTATION_E2E=1`.
- Build Docker completata. Smoke nell'immagine Linux: health live/annotazione
  senza Elasticsearch, riavvio del processo e snapshot su file con utenti
  preservati e `integrity_check=ok`. Non equivale al riavvio della VPS.

## Checklist di produzione da riconciliare con le prove del coordinatore

- [ ] Registrare modello, regione, prezzo IVA/IPv4 e commit pubblicato.
- [ ] DNS proxied, Full (strict), certificato Origin CA, redirect e cache bypass.
- [ ] Porte interne non accessibili dall'esterno; IP client e cookie Secure corretti.
- [ ] Due indici da 11.032 documenti e smoke E0–E4.
- [ ] Tre account e computer distinti; isolamento, concorrenza, ripresa e cronologia.
- [ ] Annotazione disponibile con ES arrestato.
- [ ] Nessuna perdita dopo riavvio app/VPS e aggiornamento.
- [ ] Copia dal server al PC e ripristino locale di account, giudizi e cronologia.
- [ ] Memoria, assenza OOM, tempi e salvataggi misurati sulla VPS da 2 GB.
- [ ] Istruzioni consegnate ai validatori e percorso provato prima della raccolta.

Non usare fixture per segnare questi punti come verificati su dati reali.
Il collaudo usa un archivio separato; il pilot reale resta distinto dal benchmark finale.

## Aggiornamento durante la pubblicazione

L'utente conferma health live e annotazione online, ricerca HTTP 503 su VPS
da 1 GB / 1 vCPU. I log forniti mostrano Java incapace di allocare 1 GiB,
uscita 70 e OOMKilled=false: errore di allocazione, non terminazione OOM del kernel.
Concordato rescale a 2 GB; Compose ridotto a heap 512 MiB / limite ES 1 GiB,
app 384 MiB e proxy 128 MiB. Rescale, indicizzazione e concorrenza da verificare;
queste modifiche non dichiarano ancora sostenibile il carico sulla VPS reale.
