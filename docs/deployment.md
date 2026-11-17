# Deploy automatico

Il workflow `ci.yml` richiama `deploy.yml` dopo tutti i test, esclusivamente
per push su `main`. GitHub costruisce l'immagine Linux amd64 e la trasferisce
via SSH alla VPS; non occorre un registry o un runner installato sul server.
Le esecuzioni sono serializzate e un commit superato da un nuovo push viene
saltato prima di sostituire l'applicazione.

## Attivazione

In GitHub, Settings → Secrets and variables → Actions, aggiungere:

| Secret | Valore per il server attuale |
| --- | --- |
| `DEPLOY_HOST` | `2.29.176.129` |
| `DEPLOY_USER` | `root` |
| `DEPLOY_SSH_KEY` | Contenuto completo della chiave privata SSH, senza passphrase |
| `DEPLOY_KNOWN_HOSTS` | Riga verificata di known_hosts per il server |

La chiave locale è `$HOME/.ssh/newsfinder`. Se protetta da passphrase, creare
una chiave dedicata ad Actions e aggiungerne la pubblica a `authorized_keys`.
Non inserire mai la chiave privata nel repository. Per copiare i valori negli
appunti da PowerShell senza stamparli:

```powershell
Get-Content -Raw "$HOME/.ssh/newsfinder" | Set-Clipboard
ssh-keygen -F 2.29.176.129 -f "$HOME/.ssh/known_hosts" |
    Where-Object { $_ -notmatch '^#' } | Set-Clipboard
```

Eseguire i due comandi separatamente, incollando ogni valore nel relativo secret.
Il secondo usa l'identità del server già verificata localmente, senza accettare
automaticamente una nuova host key durante il deploy.

Il job usa l'environment `production`; se si configura un'approvazione obbligatoria
su questo environment, il deploy attenderà l'approvazione. Per un flusso automatico
non impostare tale requisito. Committare e pubblicare i file su `main` per attivare
il flusso; verificarne la prima esecuzione nella scheda Actions.

## Comportamento e limiti

- Il deploy aggiorna il container `app` usando l'immagine `newsfinder-app:<SHA>`.
  Una breve interruzione durante la sostituzione del container è prevista.
- Usa il Compose già presente in `/opt/newsfinder/current`, i segreti in
  `/opt/newsfinder/production.env` e i volumi esistenti. Non aggiorna il checkout
  del server: modifiche a Compose, Caddy e infrastruttura richiedono un intervento
  esplicito, separato dal deploy dell'applicazione.
- Verifica la compatibilità del database prima della sostituzione, poi la salute
  HTTP, il database di annotazione e la connessione a Elasticsearch. Non esegue
  migrazioni automatiche né reindicizzazione del corpus.
- Se i controlli falliscono, tenta il ripristino dell'immagine precedente e
  segnala il fallimento in Actions. Non è un rollback dei dati o dello schema.
- `/opt/newsfinder/deployed-revision` viene aggiornato solo dopo i controlli.
  `bash scripts/server.sh status` e `compose` leggono questo riferimento.
- Le immagini precedenti sono conservate per il rollback. Controllare lo spazio
  con `docker system df` e rimuovere periodicamente solo i tag non più necessari,
  conservando l'immagine attiva e almeno quella precedente. Non cancellare i volumi.
- La porta SSH deve essere raggiungibile dai runner GitHub; l'accesso dal PC è
  stato verificato, quello dai runner richiede la prima esecuzione reale.

## Ripristino manuale

Sul server, scegliere lo SHA di un'immagine precedente disponibile:

```bash
cd /opt/newsfinder/current
export APP_IMAGE=newsfinder-app:SHA_PRECEDENTE
bash scripts/server.sh compose up -d --no-deps --no-build --wait app
bash scripts/server.sh compose exec -T app python -m wikinews_ir.operations check
printf '%s\n' SHA_PRECEDENTE > /opt/newsfinder/deployed-revision
```

Le migrazioni richiedono una procedura dedicata con copia manuale su PC e
verifica del ripristino, come concordato in ADR 0008.
