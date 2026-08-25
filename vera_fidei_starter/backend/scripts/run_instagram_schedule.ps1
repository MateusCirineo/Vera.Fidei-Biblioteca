$ErrorActionPreference = "Stop"

$backend = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$python = Join-Path $backend ".venv\Scripts\python.exe"
$runner = Join-Path $backend "scripts\run_instagram_agents.py"
$logDir = Join-Path $backend "data\social\logs"

if (-not (Test-Path -LiteralPath $python)) {
    throw "Ambiente Python não encontrado: $python"
}

New-Item -ItemType Directory -Force -Path $logDir | Out-Null
Set-Location -LiteralPath $backend
$stamp = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
$log = Join-Path $logDir "$stamp.log"
& $python -B $runner --scheduled *>&1 | Tee-Object -FilePath $log
exit $LASTEXITCODE
