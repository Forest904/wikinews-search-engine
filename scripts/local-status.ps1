param(
    [ValidateRange(1,65535)][int]$Port = 8000,
    [ValidateSet('ricerca','valutazione','coordinamento')][string]$Page = 'ricerca',
    [switch]$NoBrowser
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $root
try {

    $python = Join-Path $root '.venv/Scripts/python.exe'
    if (-not (Test-Path -LiteralPath $python)) { throw 'Esegui prima scripts/local-start.ps1 per preparare le dipendenze.' }
    $arguments = @((Join-Path $PSScriptRoot 'local_runtime.py'), 'status', '--port', $Port, '--page', $Page)
    if ($NoBrowser) { $arguments += '--no-browser' }
    & $python @arguments
    $result = $LASTEXITCODE
} catch {
    Write-Host $_.Exception.Message -ForegroundColor Red
    $result = 1
} finally { Pop-Location }
exit $result
