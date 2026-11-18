param([switch]$Watch)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$package = Join-Path $root 'data/processed/semantic-qwen3-06b-full'
$manifest = Get-Content -Raw -LiteralPath (Join-Path $root 'data/processed/m2-v1/manifest.json') | ConvertFrom-Json
$total = $manifest.counts.articles_produced
$counts = @{}
do {
    $blocks = @(Get-ChildItem -LiteralPath $package -Filter 'batch-*.json' | Sort-Object Name)
    $done = 0
    if ($blocks.Count) {
        # Batches commit atomically. Count the rows even if a batch contains discarded articles.
        foreach ($block in $blocks) {
            if (!$counts.ContainsKey($block.Name)) {
                $counts[$block.Name] = (Get-Content -Raw -LiteralPath $block.FullName | ConvertFrom-Json).rows.Count
            }
            $done += $counts[$block.Name]
        }
    }
    $phase = if (Test-Path (Join-Path $root 'output/semantic-full/completed.json')) { 'Trasferimento verificato' }
             elseif (Test-Path (Join-Path $package 'manifest.json')) { 'Pacchetto generato' }
             elseif (!(Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -like "*semantic generate*semantic-qwen3-06b-full*" })) {
                 $reason = Get-Content -LiteralPath (Join-Path $root 'output/semantic-full/qwen3-error.log') -ErrorAction SilentlyContinue | Select-String '^Ricerca semantica:' | Select-Object -Last 1
                 "Interrotto $reason"
             }
             else { 'Generazione (ultimo batch salvato)' }
    Write-Output ('{0:HH:mm:ss}  {1}/{2} articoli ({3:P1})  {4}' -f (Get-Date), $done, $total, ($done/$total), $phase)
    if ($Watch -and $phase -ne 'Trasferimento verificato') { Start-Sleep 30 }
} while ($Watch -and $phase -ne 'Trasferimento verificato')
