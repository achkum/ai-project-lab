$repoPath = Split-Path $PSScriptRoot
$pythonPath = python -c "import sys; print(sys.executable)"
$pythonwPath = Join-Path (Split-Path $pythonPath) 'pythonw.exe'
$workerAction = New-ScheduledTaskAction -Execute $pythonwPath -Argument '-m engine.job_worker' -WorkingDirectory $repoPath
$workerTrigger = New-ScheduledTaskTrigger -AtLogOn -User ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name)
$workerSettings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
Register-ScheduledTask -TaskName 'ai-lab-job-worker' -Action $workerAction -Trigger $workerTrigger -Settings $workerSettings -Description 'Serial subscription-only AI lab worker; VPS holds the queue while this laptop is off.' -Force -ErrorAction Stop | Out-Null
Start-ScheduledTask -TaskName 'ai-lab-job-worker'
Get-ScheduledTask -TaskName 'ai-lab-job-worker' | Select-Object TaskName,State

