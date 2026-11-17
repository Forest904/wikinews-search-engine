param(
    [ValidateRange(1,65535)][int]$Port = 8000,
    [ValidateSet('ricerca','valutazione','coordinamento')][string]$Page = 'ricerca',
    [switch]$Mock,
    [switch]$NoBrowser
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $root
try {

    & uv sync --locked
    if ($LASTEXITCODE -ne 0) { throw 'Sincronizzazione dipendenze fallita.' }

    $python = Join-Path $root '.venv/Scripts/python.exe'
    if (-not (Test-Path -LiteralPath $python)) { throw 'Esegui prima scripts/local-start.ps1 per preparare le dipendenze.' }
    $arguments = @((Join-Path $PSScriptRoot 'local_runtime.py'), 'start', '--port', $Port, '--page', $Page)
    if ($Mock) { $arguments += '--mock' }
    if ($NoBrowser) { $arguments += '--no-browser' }
    & $python @arguments
    $result = $LASTEXITCODE
} catch {
    Write-Host $_.Exception.Message -ForegroundColor Red
    $result = 1
} finally { Pop-Location }
exit $result
