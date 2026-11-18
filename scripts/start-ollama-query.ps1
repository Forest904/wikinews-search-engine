param([string]$Vps = '2.29.176.129', [switch]$AtLogon)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python = Join-Path $root '.venv/Scripts/pythonw.exe'
$script = Join-Path $PSScriptRoot 'ollama-query-tunnel.py'
$key = Join-Path $env:USERPROFILE '.ssh/newsfinder-query'
if (!(Test-Path $key) -or !(Test-Path $python)) { throw 'Chiave SSH dedicata o ambiente Python assente.' }
$arguments = '"{0}" --host "{1}" --key "{2}"' -f $script, $Vps, $key
if ($AtLogon) {
    $startup = [Environment]::GetFolderPath('Startup')
    $shortcut = (New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $startup 'NewsFinder Ollama.lnk'))
    $shortcut.TargetPath = $python
    $shortcut.Arguments = $arguments
    $shortcut.WorkingDirectory = $root
    $shortcut.Save()
}
Start-Process -FilePath $python -ArgumentList $arguments -WorkingDirectory $root -WindowStyle Hidden

