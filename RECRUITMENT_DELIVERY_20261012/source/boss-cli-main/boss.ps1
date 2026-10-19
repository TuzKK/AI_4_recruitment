$ErrorActionPreference = 'Stop'
$env:PYTHONUTF8 = '1'
$env:BOSS_BRIDGE_FILE = Join-Path $PSScriptRoot '.runtime\browser-bridge.json'
& (Join-Path $PSScriptRoot '.venv\Scripts\python.exe') -m boss_cli.cli @args
exit $LASTEXITCODE
