# Verifica M4-P — 18 novembre 2026

Due sessioni HTTP consecutive sul corpus M2 di 11.032 articoli, con Windows 11, Python 3.12.2, HTTPX 0.28.1 ed Elasticsearch 9.5.6. Tutte le 400 richieste misurate e le 80 di warmup sono riuscite.

## Riprodurre la misura

Dalla radice del repository, con il corpus preparato in `data/processed/m2-v1`, gli indici M3 disponibili e le credenziali locali configurate, avviare in un terminale l’API sul corpus reale.

```powershell
uv run --locked python -m uvicorn wikinews_ir.api.main:app --host 127.0.0.1 --port 8764 --no-access-log
```

In un secondo terminale, scegliere una nuova directory per ogni esecuzione.

```powershell
uv run --locked python scripts/benchmark_m4p.py --base-url http://127.0.0.1:8764 --output output/m4p-baseline
```

Il comando usa la porta 8000 se si omette `--base-url`. La misura documentata ha usato la 8764 perché la 8000 serviva una fixture. Il preflight confronta corpus, conteggi e identità degli indici locali con i metadati restituiti dall’API.

Ogni sessione usa una connessione HTTP persistente e percorre E0–E4 nello stesso ordine. Per ciascun profilo esegue le otto query M4 una volta per scaldare la cache e cinque volte per la misura, a pagina 1 con dieci risultati. Il timer client include la ricezione del corpo. Il tempo Elasticsearch deriva da `took`. Le misure storiche M4 cronometravano la chiamata Python diretta.


Valori in ms. Δ = sessione 2 meno sessione 1. P95 nearest-rank.

## Client HTTP

| Profilo | Richieste 1/2 | Errori misura 1/2 | Errori warmup 1/2 | Mediana 1 | Mediana 2 | Δ mediana | p95 1 | p95 2 | Δ p95 |
|---|---|---|---|---:|---:|---:|---:|---:|---:|
| E0 | 40/40 | 0/0 | 0/0 | 33.75 | 22.15 | -11.60 | 51.68 | 29.20 | -22.48 |
| E1 | 40/40 | 0/0 | 0/0 | 26.89 | 21.34 | -5.55 | 50.56 | 27.38 | -23.18 |
| E2 | 40/40 | 0/0 | 0/0 | 26.83 | 20.64 | -6.19 | 51.71 | 26.13 | -25.58 |
| E3 | 40/40 | 0/0 | 0/0 | 57.53 | 52.65 | -4.88 | 270.92 | 216.48 | -54.44 |
| E4 | 40/40 | 0/0 | 0/0 | 21.21 | 20.18 | -1.03 | 30.49 | 33.80 | 3.31 |

## Elasticsearch

| Profilo | Richieste 1/2 | Errori misura 1/2 | Errori warmup 1/2 | Mediana 1 | Mediana 2 | Δ mediana | p95 1 | p95 2 | Δ p95 |
|---|---|---|---|---:|---:|---:|---:|---:|---:|
| E0 | 40/40 | 0/0 | 0/0 | 14.50 | 4.00 | -10.50 | 30.00 | 8.00 | -22.00 |
| E1 | 40/40 | 0/0 | 0/0 | 8.50 | 4.00 | -4.50 | 31.00 | 6.00 | -25.00 |
| E2 | 40/40 | 0/0 | 0/0 | 8.00 | 4.00 | -4.00 | 20.00 | 6.00 | -14.00 |
| E3 | 40/40 | 0/0 | 0/0 | 38.00 | 35.50 | -2.50 | 237.00 | 213.00 | -24.00 |
| E4 | 40/40 | 0/0 | 0/0 | 3.00 | 3.00 | 0.00 | 12.00 | 8.00 | -4.00 |

E3 ha registrato il p95 HTTP più alto in entrambe le sessioni. La mediana client è scesa per tutti i profili nella seconda sessione. Il carico della macchina e l’ordine fisso dei profili limitano l’interpretazione delle differenze.

Gli artefatti locali sono `samples.jsonl`, `manifest.json` e `report.md` nella directory di output. Il manifest registra configurazione, versioni, identità degli indici e checksum. La baseline proviene da un checkout con modifiche locali. Il checksum SHA-256 dei campioni è `1af7eda304eea72a3acabebdf664b859f0d765031be177fc7b36870fdd5dde80`.
