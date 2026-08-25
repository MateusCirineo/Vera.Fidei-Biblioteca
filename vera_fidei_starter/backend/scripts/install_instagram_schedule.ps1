param(
    [string]$At = "12:00",
    [string]$TaskName = "VeraFidei-Instagram-Diario"
)

$ErrorActionPreference = "Stop"
$backend = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$python = Join-Path $backend ".venv\Scripts\python.exe"
$cli = Join-Path $backend "scripts\run_instagram_agents.py"
$scheduledRunner = Join-Path $backend "scripts\run_instagram_schedule.ps1"

Set-Location -LiteralPath $backend
& $python -B $cli --readiness
if ($LASTEXITCODE -ne 0) {
    throw "Agendamento não instalado: aprove a arte, rotacione as credenciais e habilite publicação/agendamento primeiro."
}

$when = [DateTime]::ParseExact($At, "HH:mm", [Globalization.CultureInfo]::InvariantCulture)
$action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$scheduledRunner`""
$trigger = New-ScheduledTaskTrigger -Daily -At $when
$taskSettings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 20)

Register-ScheduledTask `
    -TaskName $TaskName `
    -Description "Gera, valida e publica um carrossel rastreável do Vera.Fidei via API oficial." `
    -Action $action `
    -Trigger $trigger `
    -Settings $taskSettings `
    -Force | Out-Null

Write-Host "Tarefa '$TaskName' instalada para $At."
