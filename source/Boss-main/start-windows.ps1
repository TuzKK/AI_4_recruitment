$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$backendRoot = Join-Path $projectRoot 'backend'
$pythonPath = Join-Path $backendRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Missing backend virtual environment. Install backend/requirements.txt into backend/.venv first.' }
try {
    $health = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/health' -TimeoutSec 2
    if ($health.status -eq 'ok') { Write-Host 'Already running: http://127.0.0.1:8000/settings'; exit 0 }
} catch {}
$logRoot = Join-Path $backendRoot 'data\logs'
New-Item -ItemType Directory -Force -Path $logRoot | Out-Null
$serverProcess = Start-Process -FilePath $pythonPath -ArgumentList @('main.py','serve','--host','127.0.0.1','--port','8000') -WorkingDirectory $backendRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $logRoot 'server.stdout.log') -RedirectStandardError (Join-Path $logRoot 'server.stderr.log') -PassThru
$serverProcess.Id | Set-Content (Join-Path $logRoot 'server.pid')
for ($attempt=0; $attempt -lt 20; $attempt++) {
    Start-Sleep -Milliseconds 500
    try {
        if ((Invoke-RestMethod 'http://127.0.0.1:8000/api/health' -TimeoutSec 1).status -eq 'ok') {
            Write-Host 'Ready: http://127.0.0.1:8000/settings (open in your existing Chrome)'
            exit 0
        }
    } catch {}
}
throw "Server startup failed. Check $logRoot\server.stderr.log"
