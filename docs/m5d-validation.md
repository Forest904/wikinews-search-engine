# M5-D · Gold di produzione e guida al silver

## Gold verificato il 18 novembre 2026

Gli ZIP originali in `output/m5d/gold` appartengono al pacchetto congelato `m5-production-1.1`. Le assegnazioni coincidono con il piano, inclusa l’identità del valutatore. Sono stati verificati i checksum interni, il manifest di origine, le coppie per split, le revisioni e le citazioni con i loro offset. Ogni coppia assegnata ha un grado finale che coincide con i qrels.

| Split | Letture assegnate | Coppie gold | Doppie con grado concorde | Decisioni di revisione finali | Coppie del pacchetto senza gold |
|---|---:|---:|---:|---:|---:|
| Sviluppo | 139 | 116 | 18/23 | 5 | 479 |
| Test | 89 | 74 | 12/15 | 4 | 313 |

L’accordo esatto sui giudizi individuali correnti è 30/38 (78,9%). Gli otto disaccordi differiscono di un grado e hanno una decisione del terzo valutatore. La nona revisione risolve una richiesta su una coppia assegnata a un solo valutatore. La cronologia del test conserva due salvataggi `needs_review` e uno `deferred`. Nessuna coppia assegnata resta irrisolta. Le 792 coppie prive di gold restano senza giudizio umano. Tutte le 190 coppie gold sono presenti nel pacchetto silver.

SHA-256 degli ZIP originali:

- `gold-development.zip` — `df310815b75d8f3fd41c08c3e805fffa4f7ca768078963c1a9fd160541e6797e`
- `gold-test.zip` — `c40271aae53a43c89640604db1236a8f8ab15e3d232dcb6dbb92b3977ca35d4b`

## Chiusura del 19 novembre 2026

Il batch cieco ha prodotto 982 giudizi validi, 595 su sviluppo e 387 su test. La validazione completa ha verificato identificativi, revisioni, hash del testo ed evidenze. Tutte le coppie hanno ricevuto un grado. Le coppie condivise con il gold sono 116 su sviluppo e 74 su test, tutte sulla stessa revisione. Il confronto riguarda la copertura. La valutazione dei sistemi appartiene a M6-B.

L’import registra il modello dichiarato dall’operatore `GPT 6.0 Astra`, il ruolo `coordinatore` e l’esecuzione `m5d-silver-001`. La directory locale `output/m5d/m5-production-1.1` conserva gli export gold per split e i qrels silver con i rispettivi manifest. La sottocartella `silver/source` conserva il batch e il JSONL originale byte per byte, inclusi i terminatori di riga Windows. La copia testuale prodotta dalla CLI in `silver/import/original.jsonl` usa terminatori normalizzati.

L’[indice SHA-256 della versione](../benchmarks/v1/manifests/m5-production-1.1.json) identifica gli ZIP di origine, il congelamento, il batch, l’import e gli export. Per controllare tutti i riferimenti e ripetere la validazione silver, dalla radice del repository eseguire:

```powershell
$index = Get-Content benchmarks/v1/manifests/m5-production-1.1.json -Raw | ConvertFrom-Json
foreach ($entry in $index.sha256.psobject.Properties) {
    if ((Get-FileHash -LiteralPath $entry.Name -ErrorAction Stop).Hash -ne $entry.Value) {
        throw "Checksum diverso per $($entry.Name)"
    }
}
$batch = 'output/m5d/m5-production-1.1/silver/source'
uv run --locked wikinews-ir benchmark silver validate --packet $batch --judgments "$batch/judgments.jsonl"
```

## Generare il silver

1. Apri una nuova finestra di VS Code. Con **File → Apri cartella** seleziona soltanto `C:\Users\lucap\Documents\wikinews-silver-m5-production-1.1`. Il workspace contiene già il pacchetto verificato, il prompt congelato, lo schema, l’esempio sintetico e il validatore. Mantieni gold, ranking e questa guida nella cartella del coordinatore.
2. Avvia una chat Codex nuova in quella finestra. Annota il modello mostrato dal selettore, oppure `unknown` se non identificabile. Invia il messaggio qui sotto.
3. Lascia che la chat salvi i giudizi progressivamente. Se si interrompe, riprendi nella stessa chat chiedendole di validare il file parziale e completare solo le coppie mancanti. In caso di cambio di chat o modello annota il punto di ripresa e comunicalo al coordinatore per la provenienza.
4. Il controllo finale deve terminare con successo senza `--allow-partial`. Sono attesi 982 record, uno per coppia, comprese le eventuali astensioni motivate. Lascia `judgments.jsonl` nella cartella del batch.
5. Torna nella chat del coordinatore e comunica **silver pronto**, il modello dichiarato, un identificativo dell’operatore e le eventuali riprese. Il coordinatore potrà ripetere la validazione, importare con i metadati di esecuzione, esportare i qrels silver e controllare la copertura del confronto sulle 190 coppie condivise.

### Messaggio per la nuova chat

> Leggi PROMPT.md ed esegui il protocollo congelato su tutte le 982 coppie di packet.json. Lavora esclusivamente con i file di questa cartella. Per ogni coppia leggi il testo completo e applica la rubrica del topic. Salva progressivamente in judgments.jsonl. Usa il validatore portatile durante il lavoro e termina dopo che la validazione completa ha avuto successo. Riporta il numero di giudizi e di astensioni.

### Comandi di controllo nella cartella silver

```powershell
python validate.py --packet . --judgments judgments.jsonl --allow-partial
python validate.py --packet . --judgments judgments.jsonl
```
