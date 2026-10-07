# Installs the scheduled task that runs scripts/model_guard.py every minute (problem log O19).
# Run once from PowerShell:  powershell -ExecutionPolicy Bypass -File scripts\install_model_guard.ps1
$root = Split-Path -Parent $PSScriptRoot
$py = (Get-Command python).Source
$action = New-ScheduledTaskAction -Execute $py -Argument "scripts\model_guard.py" -WorkingDirectory $root
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 1)
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 3)
Register-ScheduledTask -TaskName "vinu-model-guard" -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
Write-Host "installed task vinu-model-guard (every minute); log: logs\model_guard.log"
